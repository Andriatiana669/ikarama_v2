# backend/pointages/everwin.py
"""
Affichage Everwin : une semaine de pointages (lundi → dimanche) présentée en grille, en lecture seule.

  everwin/?semaine=AAAA-MM-JJ[&employe=<id>]            (n'importe quel jour de la semaine)
  everwin/exporter/?semaine=…&employe=…                  export Excel de la grille

  - une ligne par affaire ET par tâche, avec le total de la semaine et une case par jour ;
  - case = tout le temps pointé (H_Durée + HS) ; le détail (heures, tâche, prestation, projet,
    descriptions, commentaire) est fourni pour l'icône « message » ;
  - ligne Total : « incomplet » (rouge) quand la H_Durée d'un jour ouvrable déjà commencé
    n'atteint pas 8 h.
Chaque personne voit sa semaine ; un superadmin peut choisir une autre personne (?employe=).
"""
from ikarama.temps import aujourdhui
from datetime import date as Date
from datetime import timedelta

from rest_framework.exceptions import NotFound
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from autorisations.acces import q_acces
from ikarama.vues import reponse_excel
from utilisateurs.models import Employe
from utilisateurs.serializers import EmployeResumeSerializer

from .calculs import MAX_NORMALES, est_ouvrable
from .models import Pointage

JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']


def heures(minutes):
    return round(minutes / 60, 2)


class EverwinViewSet(viewsets.ViewSet):
    """
    Affichage Everwin — module « Affichage Everwin » de Paramètres > Autorisation :
    par défaut chacun voit (et exporte) le sien ; celui des autres selon le périmètre d'un rôle.
    """
    module = 'affichage_everwin'
    verbes_actions = {'exporter': 'exporter', 'personnes': 'voir'}

    def _personne(self, request, action='voir'):
        from autorisations.droits import verifier
        moi = getattr(request.user, 'employe', None)
        identifiant = request.query_params.get('employe')
        personne = moi
        if identifiant and str(identifiant).isdigit() and moi and int(identifiant) != moi.pk:
            personne = Employe.objects.filter(q_acces()).filter(pk=identifiant).first()
            if personne is None:
                raise NotFound('Personne introuvable.')
        if personne is not None:
            verifier(request.user, 'affichage_everwin', action, personne)
        return personne

    def _peut_choisir(self, request):
        """Le périmètre « Voir » contient-il d'autres personnes que soi ? (le choix de la personne s'affiche alors)"""
        from autorisations.droits import q_droit
        moi = getattr(request.user, 'employe', None)
        return Employe.objects.filter(q_acces()).filter(q_droit(request.user, 'affichage_everwin', 'voir')).exclude(
            pk=getattr(moi, 'pk', None)).exists()

    @action(detail=False, methods=['get'])
    def personnes(self, request):
        """Recherche parmi les personnes du périmètre « Voir » (choix de la personne)."""
        from django.db.models import Q

        from autorisations.droits import q_droit
        texte = str(request.query_params.get('recherche') or '').strip()
        personnes = Employe.objects.filter(q_acces()).filter(q_droit(request.user, 'affichage_everwin', 'voir'))
        if texte:
            personnes = personnes.filter(Q(code_barre__icontains=texte) | Q(nom__icontains=texte) | Q(prenom__icontains=texte)
                                         | Q(prenom_usuel__icontains=texte))
        return Response(EmployeResumeSerializer(personnes.distinct().order_by('nom', 'prenom')[:30], many=True).data)

    def _semaine(self, request):
        try:
            jour = Date.fromisoformat(request.query_params.get('semaine') or '')
        except ValueError:
            jour = aujourdhui()
        lundi = jour - timedelta(days=jour.weekday())
        return [lundi + timedelta(days=i) for i in range(7)]

    def _grille(self, request, action='voir'):
        employe = self._personne(request, action)
        jours = self._semaine(request)
        if employe is None:
            return None
        pointages = (Pointage.objects.filter(employe=employe, date__gte=jours[0], date__lte=jours[-1])
                     .select_related('tache')
                     .prefetch_related('parts__description__projet__affaire', 'parts__description__projet__prestation')
                     .order_by('date', 'heure_debut'))

        affaires = {}
        for p in pointages:
            parts = list(p.parts.all())
            if not parts:
                continue
            projet = parts[0].description.projet
            affaire = projet.affaire
            # Une ligne par affaire et par tâche
            ligne = affaires.setdefault((affaire.id, p.tache_id), {
                'id': f'{affaire.id}-{p.tache_id}', 'affaire_id': affaire.id,
                'num_affaire': affaire.num_affaire, 'nom': affaire.nom,
                'tache': p.tache.nom, 'ordre_tache': (p.tache.ordre, p.tache_id),
                'taches': [p.tache.nom], 'total_minutes': 0, 'jours': {},
            })
            minutes = p.minutes_normales + p.minutes_hs
            ligne['total_minutes'] += minutes
            case = ligne['jours'].setdefault(p.date.isoformat(), {'minutes': 0, 'details': []})
            case['minutes'] += minutes
            case['details'].append({
                'heure_debut': p.heure_debut.strftime('%H:%M'), 'heure_fin': p.heure_fin.strftime('%H:%M'),
                'minutes': minutes, 'minutes_hs': p.minutes_hs, 'pause': p.pause, 'tache': p.tache.nom,
                'prestation': projet.prestation.nom, 'projet': projet.nom,
                'descriptions': [part.description.nom for part in parts], 'commentaire': p.commentaire,
            })

        aujourd_hui = aujourdhui()
        totaux = {}
        for jour in jours:
            du_jour = [p for p in pointages if p.date == jour]
            normales = sum(p.minutes_normales for p in du_jour)
            totaux[jour.isoformat()] = {
                'minutes': sum(p.minutes_normales + p.minutes_hs for p in du_jour),
                'minutes_normales': normales,
                # Rouge : jour ouvrable déjà commencé dont la H_Durée n'atteint pas 8 h
                'incomplet': est_ouvrable(jour) and jour <= aujourd_hui and normales < MAX_NORMALES,
            }
        lignes = sorted(affaires.values(), key=lambda a: (a['num_affaire'] or '', a['nom'], a['affaire_id'], a['ordre_tache']))
        for ligne in lignes:
            ligne.pop('ordre_tache')
        return {
            'employe': EmployeResumeSerializer(employe).data,
            'chef': EmployeResumeSerializer(employe.chef).data if employe.chef else None,
            'jours': [{'date': j.isoformat(), 'nom': JOURS[i], 'ouvrable': est_ouvrable(j)} for i, j in enumerate(jours)],
            'affaires': lignes,
            'totaux': totaux,
            'total_minutes': sum(t['minutes'] for t in totaux.values()),
            'peut_choisir': self._peut_choisir(request),
        }

    def list(self, request):
        grille = self._grille(request)
        if grille is None:
            return Response({'detail': 'Votre compte n’est relié à aucune fiche employé.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(grille)

    @action(detail=False, methods=['get'])
    def exporter(self, request):
        grille = self._grille(request, 'exporter')
        if grille is None:
            return Response({'detail': 'Aucune fiche employé.'}, status=status.HTTP_400_BAD_REQUEST)
        jours = grille['jours']
        colonnes = ([{'cle': 'affaire', 'libelle': 'Affaire'}, {'cle': 'taches', 'libelle': 'Tâche'},
                     {'cle': 'total', 'libelle': 'Total saisi (h)'}]
                    + [{'cle': j['date'], 'libelle': f"{j['nom']} {j['date'][8:10]}"} for j in jours])
        lignes = [{
            'affaire': f"{a['num_affaire']} - {a['nom']}" if a['num_affaire'] else a['nom'],
            'taches': ', '.join(a['taches']), 'total': heures(a['total_minutes']),
            **{j['date']: heures(a['jours'][j['date']]['minutes']) if j['date'] in a['jours'] else None for j in jours},
        } for a in grille['affaires']]
        lignes.append({'affaire': 'Total', 'taches': '', 'total': heures(grille['total_minutes']),
                       **{j['date']: heures(grille['totaux'][j['date']]['minutes']) for j in jours}})
        nom = f"Everwin {grille['employe']['identifiant']} {jours[0]['date']}"
        return reponse_excel(nom, colonnes, lignes)
