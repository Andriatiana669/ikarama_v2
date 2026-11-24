# backend/pointages/views.py
"""
API du pointage (préfixe /api/pointages/) — « Mon temps » : uniquement mes pointages.

  pointages/?debut=AAAA-MM-JJ&fin=AAAA-MM-JJ     mes pointages de la période (CRUD)
  pointages/resume/?debut=&fin=                   totaux et erreurs de pointage de la période
  pointages/affaires/?search=                     mes affaires, dans l'ordre de priorité du formulaire
  pointages/arborescence/?affaire=<id>            prestations > projets > descriptions de l'affaire,
                                                  avec la ligne de feuille de chaque description
  pointages/taches/                               tâches et leur type
  pointages/exporter/                             export Excel
  pointages/modele/ · pointages/importer/         import Excel (descriptions désignées par leur ID) ;
                                                  un administrateur peut importer pour n'importe qui (colonne Matricule)
"""
from datetime import date as Date
from datetime import timedelta

from django.db import transaction
from django.db.models import Exists, OuterRef, Prefetch, Q, Sum
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from autorisations.acces import q_visible
from autorisations.permissions import est_administrateur
from gsheets.models import LigneFeuille
from ikarama.importation import ColonneImport, ImportExcelMixin, lire_date, lire_heure, separer
from ikarama.vues import ExportExcelMixin, FiltresMixin
from marches.models import AffairePrestation, Description, Projet, Statut, Tache
from utilisateurs.models import Employe

from .calculs import MAX_NORMALES, creneaux_libres, est_ouvrable, minutes, suggestion
from .models import Pointage
from .serializers import PointageSerializer, TacheResumeSerializer
from .erreurs import erreurs_pointage
from .services import (COLONNES, affaires_pointables, apres_modification, descriptions_pointables,
                       infos_pour_retrait, q_place, retirer_de_la_feuille)

@transaction.atomic
def supprimer_pointage(instance):
    """Retire le temps, le commentaire et (s'il n'a plus d'autre pointage) la personne de la feuille."""
    journee, employe = (instance.employe_id, instance.date), instance.employe
    infos = infos_pour_retrait(instance)
    instance.delete()
    retirer_de_la_feuille(infos, employe)
    apres_modification([journee], infos[2])


JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']


def moi(request):
    return getattr(request.user, 'employe', None)


def employe_vise(request):
    """
    La personne dont on prépare le pointage : soi-même, ou (Pointages > Suivi) celle indiquée par ?employe=<id>,
    si on a le droit « Modifier » du Suivi sur elle.
    """
    from autorisations.droits import peut_sur
    identifiant = request.query_params.get('employe')
    if identifiant and str(identifiant).isdigit():
        personne = Employe.objects.filter(pk=identifiant).first()
        if personne and peut_sur(request.user, 'pointages_suivi', 'modifier', personne):
            return personne
    return moi(request)


def periode(request):
    """Dates de la période (?debut / ?fin), par défaut la semaine en cours jusqu'à aujourd'hui."""
    aujourd_hui = Date.today()
    try:
        debut = Date.fromisoformat(request.query_params.get('debut') or '')
    except ValueError:
        debut = aujourd_hui - timedelta(days=aujourd_hui.weekday())
    try:
        fin = Date.fromisoformat(request.query_params.get('fin') or '')
    except ValueError:
        fin = aujourd_hui
    return debut, fin


class PointageViewSet(ImportExcelMixin, FiltresMixin, ExportExcelMixin, viewsets.ModelViewSet):
    module = 'pointages'
    serializer_class = PointageSerializer
    search_fields = ['commentaire', 'tache__nom', 'parts__description__nom', 'parts__description__projet__nom',
                     'parts__description__projet__affaire__nom', 'parts__description__projet__affaire__num_affaire']
    ordering = ['date', 'heure_debut', 'id']
    filtres = {'debut': 'date__gte', 'fin': 'date__lte', 'tache': 'tache_id'}
    verbes_actions = {'resume': 'voir', 'affaires': 'voir', 'arborescence': 'voir', 'taches': 'voir', 'exporter': 'voir',
                      'creneaux': 'voir',
                      'modele': 'voir', 'importer': 'creer'}

    # --- Import Excel -----------------------------------------------------------
    import_nom = 'Pointages'
    import_colonnes = [
        ColonneImport('date', 'Date', requis=True, largeur=12, exemple='09/11/2026', aide='JJ/MM/AAAA, pas de date à venir.'),
        ColonneImport('heure_debut', 'H_Début', requis=True, largeur=10, exemple='07:30', autres_libelles=['H Debut', 'Heure début']),
        ColonneImport('heure_fin', 'H_Fin', requis=True, largeur=10, exemple='12:00', autres_libelles=['H Fin', 'Heure fin']),
        ColonneImport('tache', 'Tâche', requis=True, largeur=20, exemple='Saisie', aide='Nom d’une tâche (onglet « Tâches »).'),
        ColonneImport('descriptions', 'ID description', requis=True, largeur=16, exemple='15',
                      aide='Numéro de la description (onglet « Descriptions »). Plusieurs, séparés par « ; », '
                           'pour une tâche « Plusieurs descriptions » (même projet).',
                      autres_libelles=['ID descriptions']),
        ColonneImport('pause', 'Pause', largeur=10, exemple='Oui',
                      aide='Oui sur UN pointage par jour ouvrable : retire 1 h (sinon erreur « pause non cochée »).'),
        ColonneImport('commentaire', 'Commentaire', largeur=34),
        ColonneImport('matricule', 'Matricule', largeur=14, exemple='PR00123',
                      aide='Vide : le pointage est pour vous. Rempli : pour cette personne (administrateurs seulement ; '
                           'elle doit être responsable ou membre de l’affaire).'),
    ]
    import_explications = [
        'H_Durée et HS sont calculés automatiquement ; le temps est reporté dans les feuilles comme pour un pointage saisi.',
        'Administrateurs : indiquez le matricule pour pointer à la place d’une personne (ses affaires et ses horaires sont vérifiés).',
    ]

    def import_onglets_reference(self):
        employe = moi(self.request)
        # Droit « Importer » du Suivi : on importe aussi pour d'autres personnes (leurs affaires en cours)
        from autorisations.droits import peut, q_droit
        pour_autres = peut(self.request.user, 'pointages_suivi', 'importer')
        descriptions = (Description.objects.filter(projet__affaire__actif=True) if pour_autres
                        else descriptions_pointables(employe))
        descriptions = (descriptions.select_related('projet__affaire', 'projet__prestation')
                        .prefetch_related('lignes_feuilles__feuille')
                        .order_by('projet__affaire__nom', 'projet__prestation__nom', 'projet__nom', 'ordre', 'id'))
        lignes = [(d.id, d.projet.affaire.num_affaire, d.projet.affaire.nom, d.projet.prestation.nom, d.projet.nom, d.nom,
                   float(d.quantite) if d.quantite is not None else None, d.projet.prestation.unite,
                   ', '.join(l.feuille.nom for l in d.lignes_feuilles.all()) or 'hors feuille') for d in descriptions]
        taches = [(t.nom, t.get_type_display(), 'Oui' if t.plusieurs_descriptions else 'Non') for t in Tache.objects.order_by('ordre', 'id')]
        onglets = [
            ('Descriptions', ['ID description', 'Num affaire', 'Nom affaire', 'Prestation', 'Projet / Commune',
                              'Description', 'Quantité', 'Unité', 'Feuille'], lignes),
            ('Tâches', ['Tâche', 'Type', 'Plusieurs descriptions'], taches),
        ]
        if pour_autres:
            personnes = (Employe.objects.filter(q_visible()).filter(q_droit(self.request.user, 'pointages_suivi', 'importer'))
                         .distinct().order_by('nom', 'prenom'))
            onglets.append(('Personnes', ['Matricule', 'Nom', 'Employé'], [(e.code_barre, e.nom_affiche, e.identifiant) for e in personnes]))
        return onglets

    def _personne_pointee(self, valeurs):
        """
        La personne du pointage : soi-même, ou celle de la colonne Matricule si l'on a le droit « Importer »
        de Pointages > Suivi sur elle (Paramètres > Autorisation).
        """
        moi_ = moi(self.request)
        matricule = str(valeurs.get('matricule') or '').strip().split('_')[0].upper()
        if not matricule or (moi_ and matricule == (moi_.code_barre or '').upper()):
            return moi_
        personne = Employe.objects.filter(q_visible()).filter(code_barre__iexact=matricule).first()
        if personne is None:
            raise serializers.ValidationError({'matricule': f'matricule inconnu ou sans accès au site : « {matricule} »'})
        from autorisations.droits import peut_sur
        if not peut_sur(self.request.user, 'pointages_suivi', 'importer', personne):
            raise serializers.ValidationError({'matricule': (
                f'vous n’avez pas le droit d’importer les pointages de {personne.identifiant} '
                '(Pointages > Suivi > Importer, Paramètres > Autorisation).')})
        return personne

    def importer_ligne(self, valeurs):
        tache = Tache.objects.filter(nom__iexact=str(valeurs.get('tache') or '').strip()).first()
        if tache is None:
            raise serializers.ValidationError({'tache': f"tâche inconnue : « {valeurs.get('tache')} »"})
        try:
            ids = [int(float(i)) for i in separer(valeurs.get('descriptions'))]
        except ValueError:
            raise serializers.ValidationError({'descriptions': f"ID invalide : « {valeurs.get('descriptions')} »"})
        jour, debut, fin = lire_date(valeurs.get('date')), lire_heure(valeurs.get('heure_debut')), lire_heure(valeurs.get('heure_fin'))
        personne = self._personne_pointee(valeurs)
        serializer = PointageSerializer(data={
            'date': jour.isoformat(), 'heure_debut': debut.strftime('%H:%M'), 'heure_fin': fin.strftime('%H:%M'),
            'tache': tache.id, 'descriptions': ids, 'commentaire': str(valeurs.get('commentaire') or '').strip(),
            'pause': str(valeurs.get('pause') or '').strip().lower() in ('oui', 'o', 'x', '1', 'vrai', 'true', 'yes'),
        }, context={**self.get_serializer_context(), 'employe': personne})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        pour = '' if personne == moi(self.request) else f" ({personne.identifiant})"
        return 'creation', f"{jour:%d/%m/%Y} {debut:%H:%M}–{fin:%H:%M} {tache.nom}{pour}"

    def get_queryset(self):
        return (Pointage.objects.filter(employe=moi(self.request))
                .select_related('employe', 'tache')
                .prefetch_related('parts__description__projet__affaire', 'parts__description__projet__prestation',
                                  'parts__ligne__feuille')
                .distinct())

    def perform_destroy(self, instance):
        supprimer_pointage(instance)

    @action(detail=False, methods=['get'])
    def resume(self, request):
        debut, fin = periode(request)
        pointages = Pointage.objects.filter(employe=moi(request), date__gte=debut, date__lte=fin).order_by()
        totaux = pointages.aggregate(n=Sum('minutes_normales'), h=Sum('minutes_hs'))
        # Temps pointé par jour (H_Durée + HS)
        par_jour = {l['date']: (l['n'] or 0) + (l['h'] or 0)
                    for l in pointages.values('date').annotate(n=Sum('minutes_normales'), h=Sum('minutes_hs'))}

        erreurs = erreurs_pointage(moi(request), debut, fin)
        return Response({
            'debut': debut.isoformat(), 'fin': fin.isoformat(),
            'nb_lignes': pointages.count(),
            'minutes_normales': totaux['n'] or 0,
            'minutes_hs': totaux['h'] or 0,
            'erreurs': erreurs,
        })

    @action(detail=False, methods=['get'])
    def affaires(self, request):
        """
        Mes affaires, dans l'ordre du formulaire :
          1. je suis placé sur une ligne au statut « prioritaire au pointage »
          2. je suis placé sur une ligne
          3. une ligne a le statut prioritaire
          4. l'affaire est dans une feuille
          5. mes autres affaires
        """
        employe = employe_vise(request)
        prioritaire = Statut.prioritaire()
        lignes = LigneFeuille.objects.filter(description__projet__affaire=OuterRef('pk'))
        lignes_placees = lignes.filter(q_place(employe))
        affaires = affaires_pointables(employe).annotate(
            dans_feuille=Exists(lignes),
            place=Exists(lignes_placees),
            prioritaire=Exists(lignes.filter(statut=prioritaire)) if prioritaire else Exists(lignes.none()),
            place_prioritaire=Exists(lignes_placees.filter(statut=prioritaire)) if prioritaire else Exists(lignes.none()),
        ).order_by('-place_prioritaire', '-place', '-prioritaire', '-dans_feuille', 'nom', 'id')
        texte = request.query_params.get('search', '').strip()
        if texte:
            affaires = affaires.filter(Q(nom__icontains=texte) | Q(num_affaire__icontains=texte))
        page = self.paginate_queryset(affaires)
        donnees = [{
            'id': a.id, 'num_affaire': a.num_affaire, 'nom': a.nom,
            'dans_feuille': a.dans_feuille, 'place': a.place, 'prioritaire': a.prioritaire,
        } for a in (page if page is not None else affaires)]
        return self.get_paginated_response(donnees) if page is not None else Response(donnees)

    @action(detail=False, methods=['get'])
    def arborescence(self, request):
        """Prestations cochées > Projets / Communes > Descriptions d'une de mes affaires."""
        employe = employe_vise(request)
        affaire = affaires_pointables(employe).filter(pk=request.query_params.get('affaire')).first()
        if affaire is None:
            return Response({'detail': 'Affaire introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        # Ligne de feuille de chaque description (la plus récente si plusieurs)
        lignes = {}
        for ligne in (LigneFeuille.objects.filter(description__projet__affaire=affaire)
                      .select_related('feuille', 'statut', 'employe', 'controleur', 'employe_reprise')
                      .order_by('feuille__cree_le', 'feuille_id')):
            lignes[ligne.description_id] = ligne

        def infos_ligne(ligne):
            if ligne is None:
                return None
            return {
                'id': ligne.id, 'feuille': ligne.feuille.nom, 'numero': ligne.numero,
                'statut': {'nom': ligne.statut.nom, 'couleur': ligne.statut.couleur} if ligne.statut else None,
                'mes_roles': [t for t, (champ, _, _) in COLONNES.items() if getattr(ligne, f'{champ}_id') == employe.pk],
                'occupants': {t: (getattr(ligne, champ).identifiant if getattr(ligne, champ) else None)
                              for t, (champ, _, _) in COLONNES.items()},
            }

        projets = (Projet.objects.filter(affaire=affaire).select_related('prestation').order_by('ordre', 'id')
                   .prefetch_related(Prefetch('descriptions', queryset=Description.objects.order_by('ordre', 'id'))))
        par_prestation = {}
        for projet in projets:
            par_prestation.setdefault(projet.prestation_id, []).append({
                'id': projet.id, 'nom': projet.nom,
                'descriptions': [{
                    'id': d.id, 'nom': d.nom, 'quantite': str(d.quantite) if d.quantite is not None else None,
                    'ligne': infos_ligne(lignes.get(d.id)),
                } for d in projet.descriptions.all()],
            })
        prestations = [{
            'id': lien.prestation_id, 'nom': lien.prestation.nom, 'unite': lien.prestation.unite,
            'projets': par_prestation.get(lien.prestation_id, []),
        } for lien in AffairePrestation.objects.filter(affaire=affaire).select_related('prestation').order_by('ordre', 'id')]
        return Response({'id': affaire.id, 'num_affaire': affaire.num_affaire, 'nom': affaire.nom, 'prestations': prestations})

    @action(detail=False, methods=['get'])
    def creneaux(self, request):
        """
        GET creneaux/?date=AAAA-MM-JJ[&employe=<id>][&sauf=<id du pointage modifié>]
        Créneaux non pointés de 07h30–16h30 et heures proposées pour un nouveau pointage.
        """
        try:
            jour = Date.fromisoformat(request.query_params.get('date') or '')
        except ValueError:
            return Response({'detail': 'Date invalide.'}, status=status.HTTP_400_BAD_REQUEST)
        pointages = Pointage.objects.filter(employe=employe_vise(request), date=jour)
        if str(request.query_params.get('sauf') or '').isdigit():
            pointages = pointages.exclude(pk=request.query_params['sauf'])
        intervalles = [(minutes(p.heure_debut), minutes(p.heure_fin)) for p in pointages]
        en_heure = lambda m: None if m is None else f'{m // 60:02d}:{m % 60:02d}'
        debut, fin = suggestion(intervalles)
        return Response({
            'date': jour.isoformat(), 'ouvrable': est_ouvrable(jour),
            'occupes': [[en_heure(d), en_heure(f)] for d, f in sorted(intervalles)],
            'libres': [[en_heure(d), en_heure(f)] for d, f in creneaux_libres(intervalles)] if est_ouvrable(jour) else [],
            'suggestion': {'debut': en_heure(debut), 'fin': en_heure(fin)},
        })

    @action(detail=False, methods=['get'])
    def taches(self, request):
        return Response(TacheResumeSerializer(Tache.objects.order_by('ordre', 'id'), many=True).data)

    def list(self, request, *args, **kwargs):
        if not request.query_params.get('debut') or not request.query_params.get('fin'):
            return Response({'detail': 'Précisez la période (?debut=&fin=).'}, status=status.HTTP_400_BAD_REQUEST)
        return super().list(request, *args, **kwargs)
