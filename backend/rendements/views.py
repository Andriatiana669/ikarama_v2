# backend/rendements/views.py
"""
GET /api/rendements/parametres/   réglages des formules (toute personne connectée)
PUT /api/rendements/parametres/   modification (administrateurs)
POST /api/rendements/parametres/reinitialiser/   valeurs d'origine (administrateurs)
GET /api/rendements/analyse/?affaires=1,2&prestations=&projets=&taches=&statut=&debut=&fin=&granularite=jour|mois
GET /api/rendements/analyse/options/?affaires=&prestations=      listes des filtres
GET /api/rendements/analyse/exporter/?…                          export Excel (projets et personnes)
"""
from rest_framework.response import Response
from rest_framework.views import APIView

from autorisations.permissions import AdministrateurUniquement

from .models import ParametresRendement, tranches_par_defaut
from .serializers import ParametresRendementSerializer


class ParametresView(APIView):
    module = 'rendements'

    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH', 'POST'):
            return [AdministrateurUniquement()]
        return super().get_permissions()

    def get(self, request):
        return Response(ParametresRendementSerializer(ParametresRendement.actuels()).data)

    def put(self, request):
        serializer = ParametresRendementSerializer(ParametresRendement.actuels(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    patch = put


class ReinitialiserParametresView(APIView):
    module = 'rendements'
    permission_classes = [AdministrateurUniquement]

    def post(self, request):
        ParametresRendement.objects.filter(pk=1).delete()
        parametres = ParametresRendement.actuels()
        parametres.tranches_reprise = tranches_par_defaut()
        parametres.save()
        return Response(ParametresRendementSerializer(parametres).data)


class AnalyseView(APIView):
    """Page Rendement : histogramme des projets, rendement des équipes, évolution par personne."""
    module = 'rendements'

    def get(self, request):
        from .analyse import analyser
        return Response(analyser(request.user, request.query_params))


class OptionsAnalyseView(APIView):
    module = 'rendements'

    def get(self, request):
        from .analyse import options
        return Response(options(request.user, request.query_params))


class ExportAnalyseView(APIView):
    module = 'rendements'

    def get(self, request):
        from ikarama.vues import reponse_excel

        from .analyse import analyser
        donnees = analyser(request.user, request.query_params)
        colonnes = [{'cle': c, 'libelle': l} for c, l in (
            ('type', 'Type'), ('nom', 'Nom'), ('unite', 'Unité'), ('quantite', 'Quantité'),
            ('heures', 'Heures pointées'), ('rendement', 'Rendement / j'), ('objectif', 'Objectif / j'))]
        arrondi = lambda v: round(v, 2) if v else None
        types = {'prestations': 'Prestation', 'projets': 'Projet / Commune', 'descriptions': 'Description'}
        lignes = [{**b, 'type': types.get(donnees['niveau'], ''), 'rendement': arrondi(b['rendement'])} for b in donnees['barres']]
        lignes += [{'type': 'Personne', 'nom': p['nom_affiche'], 'unite': donnees['unite'] or '', 'quantite': p['quantite'],
                    'heures': p['heures'], 'rendement': arrondi(p['rendement']), 'objectif': None} for p in donnees['personnes']]
        e = donnees['equipes']
        if e:
            lignes.insert(0, {'type': 'Global', 'nom': 'Global', 'unite': donnees['unite'] or 'unités différentes',
                              'quantite': e['quantite'], 'heures': e['heures'],
                              'rendement': arrondi(e['rendement']), 'objectif': arrondi(e['objectif'])})
        return reponse_excel('Rendement', colonnes, lignes)


class GlobaleView(APIView):
    """Rendement > Globale : histogramme par employé, camemberts, rentabilités."""
    module = 'rendements'

    def get(self, request):
        from .analyse import globale
        return Response(globale(request.user, request.query_params))


class ExportGlobaleView(APIView):
    module = 'rendements'

    def get(self, request):
        from ikarama.vues import reponse_excel

        from .analyse import globale
        donnees = globale(request.user, request.query_params)
        arrondi = lambda v, n=2: round(v, n) if v is not None else None
        colonnes = [{'cle': c, 'libelle': l} for c, l in (
            ('identifiant', 'Employé'), ('quantite', 'Quantité'), ('heures', 'Heures pointées'),
            ('rendement', 'Rendement moyen / j'), ('objectif', 'Objectif / j'), ('rentabilite', 'Rentabilité'))]
        lignes = [{**e, 'rendement': arrondi(e['rendement']), 'objectif': arrondi(e['objectif']),
                   'rentabilite': arrondi(e['rentabilite'])} for e in donnees['employes']]
        return reponse_excel('Rendement globale', colonnes, lignes)


class EvolutionView(APIView):
    """Rendement > Evolution : deux courbes de rendement par date pointée (+ tableaux de Globale)."""
    module = 'rendements'

    def get(self, request):
        from .analyse import evolution
        return Response(evolution(request.user, request.query_params))


class ExportEvolutionView(APIView):
    module = 'rendements'

    def get(self, request):
        from ikarama.vues import reponse_excel

        from .analyse import evolution
        donnees = evolution(request.user, request.query_params)
        colonnes = [{'cle': 'date', 'libelle': 'Date'}] + [
            {'cle': f'c{i}', 'libelle': f"{c['nom']} ({', '.join(t['nom'] for t in c['taches']) or 'toutes les tâches'})"}
            for i, c in enumerate(donnees['courbes'])]
        lignes = [{'date': d, **{f'c{i}': round(c['valeurs'][j], 2) if c['valeurs'][j] is not None else None
                                 for i, c in enumerate(donnees['courbes'])}} for j, d in enumerate(donnees['dates'])]
        return reponse_excel('Rendement evolution', colonnes, lignes)


class ParametresGraphiquesView(APIView):
    """
    Paramètres > Graphiques. Lecture : toute personne qui voit le Rendement ; modification : administrateurs.
    """
    module = 'rendements'
    SEUILS = {'analyse_seuil_temps': (1, 100), 'analyse_seuil_aide': (1, 100), 'analyse_mois_adaptation': (1, 24),
              'analyse_seuil_baisse': (1, 100)}

    def _donnees(self, p):
        taches = lambda relation: list(relation.order_by('ordre', 'id').values_list('id', flat=True))
        return {
            'taches_camembert': taches(p.taches_camembert),
            'courbe1_nom': p.courbe1_nom, 'courbe1_couleur': p.courbe1_couleur, 'courbe1_taches': taches(p.courbe1_taches),
            'courbe2_nom': p.courbe2_nom, 'courbe2_couleur': p.courbe2_couleur, 'courbe2_taches': taches(p.courbe2_taches),
            'barre1_nom': p.barre1_nom, 'barre1_couleur': p.barre1_couleur, 'barre1_taches': taches(p.barre1_taches),
            'barre2_nom': p.barre2_nom, 'barre2_couleur': p.barre2_couleur, 'barre2_taches': taches(p.barre2_taches),
            **{c: getattr(p, c) for c in self.SEUILS},
            'donnees_feuilles': p.donnees_feuilles,
            'donnees_pointages': p.donnees_pointages,
            'synchronisation': p.synchronisation,
        }

    def get(self, request):
        from .models import ParametresGraphiques
        return Response(self._donnees(ParametresGraphiques.actuels()))

    def put(self, request):
        import re

        from autorisations.permissions import est_administrateur
        from marches.models import Tache

        from .models import ParametresGraphiques
        if not est_administrateur(request.user):
            return Response({'detail': 'Réservé aux administrateurs.'}, status=403)
        p = ParametresGraphiques.actuels()
        erreurs = {}
        for prefixe in ('courbe1', 'courbe2', 'barre1', 'barre2'):
            nom = str(request.data.get(f'{prefixe}_nom', getattr(p, f'{prefixe}_nom'))).strip()
            couleur = str(request.data.get(f'{prefixe}_couleur', getattr(p, f'{prefixe}_couleur'))).strip()
            if not nom:
                erreurs[f'{prefixe}_nom'] = ['Donnez un nom.']
            if not re.fullmatch(r'#[0-9A-Fa-f]{6}', couleur):
                erreurs[f'{prefixe}_couleur'] = ['Couleur au format #RRGGBB.']
            setattr(p, f'{prefixe}_nom', nom[:60])
            setattr(p, f'{prefixe}_couleur', couleur.upper())
        for champ, (mini, maxi) in self.SEUILS.items():
            if champ in request.data:
                try:
                    valeur = int(request.data[champ])
                    assert mini <= valeur <= maxi
                    setattr(p, champ, valeur)
                except (TypeError, ValueError, AssertionError):
                    erreurs[champ] = [f'Nombre entier de {mini} à {maxi}.']
        if 'donnees_feuilles' in request.data:
            p.donnees_feuilles = bool(request.data.get('donnees_feuilles'))
        if 'donnees_pointages' in request.data:
            p.donnees_pointages = bool(request.data.get('donnees_pointages'))
        if 'synchronisation' in request.data:
            p.synchronisation = bool(request.data.get('synchronisation'))
        if erreurs:
            return Response(erreurs, status=400)
        p.save()
        for champ in ('taches_camembert', 'courbe1_taches', 'courbe2_taches', 'barre1_taches', 'barre2_taches'):
            if champ in request.data:
                getattr(p, champ).set(Tache.objects.filter(pk__in=[i for i in request.data.get(champ) or [] if str(i).isdigit()]))
        return Response(self._donnees(p))


class ReelObjectifView(APIView):
    """Rendement > Réel vs Objectif : deux barres par employé (groupes de tâches de Paramètres > Graphiques)."""
    module = 'rendements'

    def get(self, request):
        from .analyse import reel_objectif
        return Response(reel_objectif(request.user, request.query_params))


class ExportReelObjectifView(APIView):
    module = 'rendements'

    def get(self, request):
        from ikarama.vues import reponse_excel

        from .analyse import reel_objectif
        donnees = reel_objectif(request.user, request.query_params)
        arrondi = lambda v: round(v, 2) if v is not None else None
        reel, objectif = donnees['barres']
        colonnes = [{'cle': c, 'libelle': l} for c, l in (
            ('identifiant', 'Employé'), ('quantite', 'Quantité'), ('heures', 'Heures pointées'),
            ('rendement', f"{reel['nom']} (réel / j)"), ('objectif', f"{objectif['nom']} (objectif / j)"), ('rentabilite', 'Rentabilité'))]
        lignes = [{**e, 'rendement': arrondi(e['rendement']), 'objectif': arrondi(e['objectif']),
                   'rentabilite': arrondi(e['rentabilite'])} for e in donnees['employes']]
        return reponse_excel('Reel vs objectif', colonnes, lignes)


class EvaluationView(APIView):
    """Rendement > Evaluation Employé : rendement moyen des employés par mois de pointage."""
    module = 'rendements'

    def get(self, request):
        from .analyse import evaluation
        return Response(evaluation(request.user, request.query_params))


class ExportEvaluationView(APIView):
    module = 'rendements'

    def get(self, request):
        from ikarama.vues import reponse_excel

        from .analyse import evaluation
        donnees = evaluation(request.user, request.query_params)
        colonnes = [{'cle': c, 'libelle': l} for c, l in (
            ('mois', 'Mois'), ('employe', 'Employé'), ('rendement', 'Rendement moyen / j'), ('objectif', 'Objectif / j'))]
        lignes = []
        for m in donnees['mois']:
            for e in m['employes']:
                objectifs = [o['objectif'] for o in e['objectifs']]
                lignes.append({'mois': m['mois'], 'employe': e['identifiant'], 'rendement': round(e['rendement'], 2),
                               'objectif': round(sum(objectifs) / len(objectifs), 2)})
            lignes.append({'mois': m['mois'], 'employe': 'Moyenne', 'rendement': round(m['rendement'], 2), 'objectif': None})
        return reponse_excel('Evaluation employe', colonnes, lignes)


class AnalyseEmployesView(APIView):
    """Rendement > Analyse : temps et rentabilité des employés par affaire / prestation, mois par mois."""
    module = 'rendements'

    def get(self, request):
        from .analyse import analyse_employes
        return Response(analyse_employes(request.user, request.query_params))


class ExportAnalyseEmployesView(APIView):
    module = 'rendements'

    def get(self, request):
        from ikarama.vues import reponse_excel

        from .analyse import analyse_employes
        donnees = analyse_employes(request.user, request.query_params)
        colonnes = [{'cle': c, 'libelle': l} for c, l in (
            ('employe', 'Employé'), ('mois', 'Mois'), ('affaire', 'Affaire'), ('prestation', 'Prestation'), ('heures', 'Heures'),
            ('part', '% du temps'), ('heures_aide', "Heures d'aide"), ('rendement', 'Rendement / j'), ('objectif', 'Objectif / j'),
            ('rentabilite', 'Rentabilité'), ('zone', 'Zone'), ('badges', 'Signaux'))]
        lignes = []
        for e in donnees['employes']:
            for l in e['suivi']['lignes']:
                for mois, c in l['cases'].items():
                    lignes.append({
                        'employe': e['identifiant'], 'mois': mois, 'affaire': l['affaire'], 'prestation': l['prestation'],
                        'heures': c['heures'], 'part': round(c['part'] * 100, 1), 'heures_aide': c['heures_aide'],
                        'rendement': round(c['rendement'], 2) if c['rendement'] is not None else None,
                        'objectif': round(c['objectif'], 2) if c['objectif'] is not None else None,
                        'rentabilite': round(c['rentabilite'], 2) if c['rentabilite'] is not None else None,
                        'zone': c['zone'], 'badges': ', '.join(b['libelle'] for b in c['badges']),
                    })
        return reponse_excel('Analyse employes', colonnes, lignes)
