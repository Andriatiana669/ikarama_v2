# backend/planning/views.py
"""
API du Planning Projet (préfixe /api/planning/) — module « Planning Projet » de Paramètres > Autorisation :
par défaut chacun voit son propre planning ; voir l'équipe et planifier passent par un rôle (périmètre de personnes).

  GET    semaine/?debut=AAAA-MM-JJ&semaines=8     la grille de plusieurs semaines (une ligne par personne du périmètre)
  GET    semaine/exporter/?debut=&semaines=       la même grille en Excel
  GET    projets/?recherche=                      les projets / communes que l'on peut planifier
  POST   affectations/       {employe, date, projet}       planifier (aujourd'hui ou plus tard)
  PATCH  affectations/<id>/  {employe?, date?}             déplacer
  DELETE affectations/<id>/                                retirer
« En train de faire » : les lignes de feuille au statut qui a le rôle « En train de faire » (Marchés > Statuts).

Une case : le passé et aujourd'hui viennent des pointages (projets pointés, heures) ; aujourd'hui et l'avenir
montrent aussi ce qui est planifié.
"""
from collections import defaultdict
from datetime import date as Date
from datetime import timedelta

from django.db.models import Q
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from autorisations.acces import q_acces
from autorisations.droits import peut, peut_sur, q_droit, verifier
from autorisations.permissions import est_administrateur
from ikarama.vues import reponse_excel
from marches.models import Affaire, Projet, Statut
from pointages.calculs import est_ouvrable
from pointages.models import PartPointage
from utilisateurs.models import Employe
from utilisateurs.serializers import EmployeResumeSerializer

from .models import AffectationPlanning

JOURS = ['Lun.', 'Mar.', 'Mer.', 'Jeu.', 'Ven.', 'Sam.', 'Dim.']
MODULE = 'planning_projet'


MAX_SEMAINES = 26


def lundi_de(texte):
    try:
        jour = Date.fromisoformat(texte or '')
    except ValueError:
        jour = Date.today()
    return jour - timedelta(days=jour.weekday())


def plage(parametres):
    """Du lundi de ?debut= (ou de ?semaine=) sur ?semaines= semaines (1 à 26 ; 1 par défaut)."""
    lundi = lundi_de(parametres.get('debut') or parametres.get('semaine'))
    try:
        semaines = max(1, min(MAX_SEMAINES, int(parametres.get('semaines') or 1)))
    except ValueError:
        semaines = 1
    return lundi, semaines


def nom_projet(projet):
    return {'projet_id': projet.id, 'projet': projet.nom, 'affaire': projet.affaire.nom,
            'num_affaire': projet.affaire.num_affaire, 'prestation': projet.prestation.nom}


JOURS_ALERTE = 7   # une échéance à 7 jours ou moins est « proche »


def etat_echeances(projets):
    """
    Pour chaque projet : avancement moyen de ses lignes de feuille, terminé ou non, et état de l'échéance :
      'retard'  date de livraison passée et pas terminé ;
      'proche'  livraison dans 7 jours ou moins et pas terminé ;
      'termine' toutes ses lignes au statut qui active la note de rendement (ou à 100 %) ;
      'ok'      sinon.
    """
    from django.db.models import Avg, Count

    from gsheets.models import LigneFeuille
    aujourd_hui = Date.today()
    statut_final = Statut.pour_note_rendement()
    fini = Q(avancement__gte=100) | (Q(statut=statut_final) if statut_final else Q(pk__in=[]))
    stats = {s['description__projet_id']: s for s in LigneFeuille.objects.filter(description__projet__in=projets)
             .values('description__projet_id').annotate(moyenne=Avg('avancement'), lignes=Count('id'),
                                                        finies=Count('id', filter=fini))}
    resultat = {}
    for p in projets:
        st = stats.get(p.id, {})
        termine = bool(st.get('lignes')) and st.get('finies') == st.get('lignes')
        if termine:
            etat = 'termine'
        elif p.date_livraison and p.date_livraison < aujourd_hui:
            etat = 'retard'
        elif p.date_livraison and (p.date_livraison - aujourd_hui).days <= JOURS_ALERTE:
            etat = 'proche'
        else:
            etat = 'ok'
        resultat[p.id] = {'date_livraison': p.date_livraison.isoformat() if p.date_livraison else None,
                          'avancement': round(st.get('moyenne') or 0), 'etat': etat}
    return resultat


def personnes_du_planning(user, recherche=''):
    personnes = Employe.objects.filter(q_acces()).filter(q_droit(user, MODULE, 'voir'))
    if recherche:
        personnes = personnes.filter(Q(code_barre__icontains=recherche) | Q(nom__icontains=recherche)
                                     | Q(prenom__icontains=recherche) | Q(prenom_usuel__icontains=recherche))
    return personnes.distinct().order_by('nom', 'prenom')


def chaine_des_chefs(personne, chefs):
    """Les responsables successifs (N+1, N+2…) : sert au filtre « Équipe de » (sous-équipes comprises)."""
    resultat, vus = [], set()
    courant = chefs.get(personne)
    while courant and courant not in vus:
        resultat.append(courant)
        vus.add(courant)
        courant = chefs.get(courant)
    return resultat


def grille(user, lundi, semaines=1, recherche=''):
    from gsheets.models import LigneFeuille
    jours = [lundi + timedelta(days=i) for i in range(7 * semaines)]
    aujourd_hui = Date.today()
    personnes = list(personnes_du_planning(user, recherche).prefetch_related('postes')[:300])
    ids = [p.pk for p in personnes]
    chefs = dict(Employe.objects.exclude(chef__isnull=True).values_list('pk', 'chef_id'))

    # Passé et aujourd'hui : les pointages (projet, heures)
    pointe = defaultdict(lambda: defaultdict(dict))
    for part in (PartPointage.objects.filter(pointage__employe_id__in=ids, pointage__date__gte=jours[0],
                                             pointage__date__lte=min(jours[-1], aujourd_hui))
                 .select_related('pointage', 'description__projet__affaire', 'description__projet__prestation')):
        projet = part.description.projet
        case = pointe[part.pointage.employe_id][part.pointage.date.isoformat()]
        element = case.setdefault(projet.id, {**nom_projet(projet), 'affaire_id': projet.affaire_id, 'minutes': 0})
        element['minutes'] += part.minutes_normales + part.minutes_hs

    # Aujourd'hui et l'avenir : le planifié
    prevu = defaultdict(lambda: defaultdict(list))
    for a in (AffectationPlanning.objects.filter(employe_id__in=ids, date__gte=max(jours[0], aujourd_hui), date__lte=jours[-1])
              .select_related('projet__affaire', 'projet__prestation')):
        prevu[a.employe_id][a.date.isoformat()].append(
            {'id': a.id, **nom_projet(a.projet), 'affaire_id': a.projet.affaire_id, 'commentaire': a.commentaire})

    # En train de faire : lignes de feuille au statut « En train de faire » (Employé, Contrôleur ou Employé reprise)
    statut = Statut.pour_en_train_de_faire()
    en_cours = defaultdict(list)
    if statut:
        for ligne in (LigneFeuille.objects.filter(statut=statut, description__isnull=False)
                      .filter(Q(employe_id__in=ids) | Q(controleur_id__in=ids) | Q(employe_reprise_id__in=ids))
                      .select_related('description__projet__affaire', 'description__projet__prestation')):
            for personne_id in {ligne.employe_id, ligne.controleur_id, ligne.employe_reprise_id} & set(ids):
                if len(en_cours[personne_id]) < 4:
                    en_cours[personne_id].append({**nom_projet(ligne.description.projet), 'affaire_id': ligne.description.projet.affaire_id,
                                                  'description': ligne.description.nom})

    # Disponibilités : jours ouvrables des 14 prochains jours sans rien de pointé ni de planifié
    prochains = [aujourd_hui + timedelta(days=i) for i in range(14)]
    prevus_proches = defaultdict(set)
    for employe_id, jour in AffectationPlanning.objects.filter(employe_id__in=ids, date__gte=aujourd_hui,
                                                                date__lte=prochains[-1]).values_list('employe_id', 'date'):
        prevus_proches[employe_id].add(jour)
    pointe_aujourdhui = set(PartPointage.objects.filter(pointage__employe_id__in=ids, pointage__date=aujourd_hui)
                            .values_list('pointage__employe_id', flat=True))

    lignes = []
    for p in personnes:
        cases = {}
        for jour in jours:
            cle = jour.isoformat()
            pointes = sorted(pointe[p.pk][cle].values(), key=lambda x: -x['minutes']) if jour <= aujourd_hui else []
            cases[cle] = {'pointe': pointes, 'prevu': prevu[p.pk][cle] if jour >= aujourd_hui else []}
        libres = [j.isoformat() for j in prochains if est_ouvrable(j) and j not in prevus_proches[p.pk]
                  and not (j == aujourd_hui and p.pk in pointe_aujourdhui)]
        postes = list(p.postes.all())
        lignes.append({
            'employe': EmployeResumeSerializer(p).data, 'cases': cases, 'en_cours': en_cours.get(p.pk, []),
            'jours_libres': libres,
            'poles': sorted({x.pole for x in postes if x.pole}), 'postes': sorted({x.poste_nom for x in postes if x.poste_nom}),
            'chefs': chaine_des_chefs(p.pk, chefs),
            'planifiable': peut_sur(user, MODULE, 'creer', p),
        })
    # Échéances : projets des affaires en cours visibles dont la livraison tombe dans la plage
    moi = getattr(user, 'employe', None)
    affaires = Affaire.objects.filter(actif=True)
    if not est_administrateur(user):
        affaires = affaires.filter(Q(responsables=moi) | Q(membres=moi) | q_droit(user, 'marches_projets', 'voir'))
    a_livrer = list(Projet.objects.filter(affaire__in=affaires.distinct(), date_livraison__gte=jours[0], date_livraison__lte=jours[-1])
                    .select_related('affaire', 'prestation'))
    etats = etat_echeances(a_livrer)
    echeances = defaultdict(list)
    for p in a_livrer:
        echeances[p.date_livraison.isoformat()].append({**nom_projet(p), 'affaire_id': p.affaire_id, **etats[p.id]})

    return {
        'echeances': echeances,
        'debut': jours[0].isoformat(), 'fin': jours[-1].isoformat(), 'aujourdhui': aujourd_hui.isoformat(),
        'semaines': [{'numero': int(jours[7 * i].strftime('%V')), 'annee': int(jours[7 * i].strftime('%G')),
                      'debut': jours[7 * i].isoformat()} for i in range(semaines)],
        'jours': [{'date': j.isoformat(), 'nom': JOURS[j.weekday()], 'ouvrable': est_ouvrable(j), 'passe': j < aujourd_hui,
                   'aujourdhui': j == aujourd_hui} for j in jours],
        'statut_en_cours': {'id': statut.id, 'nom': statut.nom, 'couleur': statut.couleur} if statut else None,
        'lignes': lignes,
        'droits': {a: peut(user, MODULE, a) for a in ('creer', 'modifier', 'supprimer', 'exporter')},
    }


class SemaineView(APIView):
    def get(self, request):
        verifier(request.user, MODULE, 'voir')
        lundi, semaines = plage(request.query_params)
        return Response(grille(request.user, lundi, semaines, str(request.query_params.get('recherche') or '').strip()))


class ExportSemaineView(APIView):
    def get(self, request):
        verifier(request.user, MODULE, 'exporter')
        lundi, semaines = plage(request.query_params)
        donnees = grille(request.user, lundi, semaines)
        # Exporter : seulement les personnes du périmètre « Exporter »
        exportables = set(Employe.objects.filter(q_droit(request.user, MODULE, 'exporter')).values_list('pk', flat=True))
        colonnes = [{'cle': 'employe', 'libelle': 'Employé'}, {'cle': 'en_cours', 'libelle': 'En train de faire'}] + [
            {'cle': j['date'], 'libelle': f"{j['nom']} {Date.fromisoformat(j['date']):%d/%m/%Y}"} for j in donnees['jours']]
        lignes = []
        for l in donnees['lignes']:
            if l['employe']['id'] not in exportables:
                continue
            ligne = {'employe': l['employe']['identifiant'],
                     'en_cours': ' ; '.join(f"{e['projet']} ({e['description']})" for e in l['en_cours'])}
            for jour, case in l['cases'].items():
                textes = [f"{e['projet']} {e['minutes'] / 60:g} h".replace('.', ',') for e in case['pointe']]
                textes += [f"Prévu : {e['projet']}" for e in case['prevu']]
                ligne[jour] = ' ; '.join(textes)
            lignes.append(ligne)
        return reponse_excel(f"Planning S{donnees['semaines'][0]['numero']}", colonnes, lignes)


class ProjetsPlanifiablesView(APIView):
    """Projets / communes des affaires en cours que l'on peut voir (responsable, membre ; tout pour le superadmin)."""
    def get(self, request):
        verifier(request.user, MODULE, 'voir')
        moi = getattr(request.user, 'employe', None)
        affaires = Affaire.objects.filter(actif=True)
        if not est_administrateur(request.user):
            affaires = affaires.filter(Q(responsables=moi) | Q(membres=moi) | q_droit(request.user, 'marches_projets', 'voir'))
        projets = Projet.objects.filter(affaire__in=affaires.distinct()).select_related('affaire', 'prestation')
        texte = str(request.query_params.get('recherche') or '').strip()
        if texte:
            projets = projets.filter(Q(nom__icontains=texte) | Q(affaire__nom__icontains=texte)
                                     | Q(affaire__num_affaire__icontains=texte) | Q(prestation__nom__icontains=texte))
        projets = list(projets.order_by('affaire__nom', 'prestation__nom', 'ordre', 'id')[:300])
        etats = etat_echeances(projets)
        return Response([{**nom_projet(p), 'affaire_id': p.affaire_id, **etats[p.id]} for p in projets])


class AffectationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AffectationPlanning
        fields = ['id', 'employe', 'date', 'projet', 'commentaire']

    def validate_date(self, valeur):
        if valeur < Date.today():
            raise serializers.ValidationError('On ne planifie que pour aujourd’hui ou plus tard (le passé vient des pointages).')
        return valeur

    def validate_projet(self, projet):
        if not projet.affaire.actif:
            raise serializers.ValidationError('Cette affaire est archivée.')
        return projet

    def validate(self, donnees):
        employe = donnees.get('employe', getattr(self.instance, 'employe', None))
        date = donnees.get('date', getattr(self.instance, 'date', None))
        projet = donnees.get('projet', getattr(self.instance, 'projet', None))
        doublon = AffectationPlanning.objects.filter(employe=employe, date=date, projet=projet)
        if self.instance:
            doublon = doublon.exclude(pk=self.instance.pk)
        if doublon.exists():
            raise serializers.ValidationError('Ce projet est déjà planifié pour cette personne ce jour-là.')
        return donnees


class AffectationViewSet(viewsets.GenericViewSet):
    serializer_class = AffectationSerializer
    queryset = AffectationPlanning.objects.select_related('employe', 'projet__affaire')

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verifier(request.user, MODULE, 'creer', serializer.validated_data['employe'])
        moi = getattr(request.user, 'employe', None)
        affectation = serializer.save(cree_par=moi)
        self._prevenir(affectation, moi)
        return Response(self.get_serializer(affectation).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        affectation = self.get_object()
        verifier(request.user, MODULE, 'modifier', affectation.employe)
        if affectation.date < Date.today():
            return Response({'detail': 'Une journée passée ne se modifie plus.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(affectation, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if 'employe' in serializer.validated_data:
            verifier(request.user, MODULE, 'modifier', serializer.validated_data['employe'])
        affectation = serializer.save()
        return Response(self.get_serializer(affectation).data)

    def destroy(self, request, pk=None):
        affectation = self.get_object()
        verifier(request.user, MODULE, 'supprimer', affectation.employe)
        affectation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def _prevenir(affectation, auteur):
        """La personne planifiée par quelqu'un d'autre est prévenue (cloche)."""
        if auteur is None or auteur.pk == affectation.employe_id:
            return
        from notifications.services import notifier
        notifier([affectation.employe_id], 'affaire',
                 f"Planifié : {affectation.projet.nom} le {affectation.date:%d/%m/%Y}",
                 message=f"{affectation.projet.affaire.nom}, par {auteur.identifiant}.", lien='/planning-projet')
