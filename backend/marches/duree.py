# backend/marches/duree.py
"""
Marchés > Durée estimatif : combien de temps pour traiter chaque Projet / Commune.

  Temps estimatif (heures)  = Σ quantités des descriptions retenues ÷ rendement objectif par jour × heures par jour
  Temps restant (heures)    = même calcul sur la quantité restante (quantité × (100 − avancement de sa ligne) %)
  Durée                     = temps ÷ ressources disponibles (nombre de personnes ; simulation saisie à l'écran)
Heures par jour : Paramètres > Rendement & Note.

  GET duree-estimative/?affaires=&prestations=&statuts=&descriptions=&rendements=
  GET duree-estimative/exporter/?…&ressources={"<projet_id>": 3, …}&unite=jours|heures
Filtres (listes cochées ; aucune = tout) : affaires, prestations, rendements objectifs (projets qui les ont),
descriptions (seulement celles-ci) et statuts (descriptions dont la ligne de feuille a ce statut).
Accès : module « Marchés > Durée estimatif » de Paramètres > Autorisation (Voir, Exporter ; périmètre d'affaires).
"""
import json
from decimal import Decimal

from django.db.models import Q
from rest_framework.response import Response
from rest_framework.views import APIView

from autorisations.droits import q_droit, verifier

from .models import Affaire, Description, Projet, Statut

MODULE = 'marches_duree'


def _ids(valeur):
    return [int(x) for x in str(valeur or '').split(',') if x.strip().isdigit()]


def calculer(user, parametres, action='voir'):
    from gsheets.models import LigneFeuille
    from rendements.models import ParametresRendement
    h = ParametresRendement.actuels().heures_par_jour

    affaires_visibles = Affaire.objects.filter(actif=True).filter(q_droit(user, MODULE, action))
    projets = Projet.objects.filter(affaire__in=affaires_visibles).select_related('affaire', 'prestation', 'rendement')
    # Listes proposées (avant les filtres qui les concernent)
    options_affaires = affaires_visibles.distinct().order_by('nom')
    if _ids(parametres.get('affaires')):
        projets = projets.filter(affaire_id__in=_ids(parametres['affaires']))
    options_prestations = {p.prestation_id: p.prestation for p in projets}
    if _ids(parametres.get('prestations')):
        projets = projets.filter(prestation_id__in=_ids(parametres['prestations']))
    options_rendements = {p.rendement_id: p.rendement for p in projets if p.rendement_id}
    if _ids(parametres.get('rendements')):
        projets = projets.filter(rendement_id__in=_ids(parametres['rendements']))
    projets = list(projets.order_by('affaire__nom', 'prestation__nom', 'ordre', 'id'))

    descriptions = Description.objects.filter(projet__in=projets).order_by('projet_id', 'ordre', 'id')
    lignes = {l.description_id: l for l in LigneFeuille.objects.filter(description__in=descriptions).select_related('statut')}
    options_descriptions = list(descriptions)
    if _ids(parametres.get('descriptions')):
        descriptions = descriptions.filter(pk__in=_ids(parametres['descriptions']))
    statuts = _ids(parametres.get('statuts'))
    retenues = [d for d in descriptions if not statuts or (d.id in lignes and lignes[d.id].statut_id in statuts)]

    par_projet = {}
    for d in retenues:
        quantite = Decimal(d.quantite or 0)
        ligne = lignes.get(d.id)
        avancement = Decimal(ligne.avancement or 0) if ligne else Decimal(0)
        stats = par_projet.setdefault(d.projet_id, {'quantite': Decimal(0), 'restante': Decimal(0), 'nb': 0})
        stats['quantite'] += quantite
        stats['restante'] += quantite * (Decimal(100) - min(avancement, Decimal(100))) / Decimal(100)
        stats['nb'] += 1

    resultat = []
    for p in projets:
        stats = par_projet.get(p.id)
        if not stats:
            continue
        objectif = Decimal(p.rendement.valeur) if p.rendement_id and p.rendement.valeur else None
        temps = (stats['quantite'] / objectif * h) if objectif else None
        reste = (stats['restante'] / objectif * h) if objectif else None
        resultat.append({
            'id': p.id, 'nom': p.nom, 'affaire': p.affaire.nom, 'num_affaire': p.affaire.num_affaire,
            'prestation': p.prestation.nom, 'unite': p.prestation.unite,
            'rendement_objectif': float(objectif) if objectif else None, 'nb_descriptions': stats['nb'],
            'quantite': float(stats['quantite']), 'quantite_restante': float(round(stats['restante'], 2)),
            # 4 décimales : un très petit temps (ex. 1 lot) ne doit pas devenir 0
            'temps_heures': float(round(temps, 4)) if temps is not None else None,
            'temps_restant_heures': float(round(reste, 4)) if reste is not None else None,
            'date_livraison': p.date_livraison.isoformat() if p.date_livraison else None,
        })
    return {
        'heures_par_jour': float(h),
        'projets': resultat,
        'options': {
            'affaires': [{'id': a.id, 'nom': f'{a.num_affaire} - {a.nom}' if a.num_affaire else a.nom} for a in options_affaires],
            'prestations': sorted([{'id': p.id, 'nom': p.nom} for p in options_prestations.values()], key=lambda x: x['nom']),
            'rendements': sorted([{'id': r.id, 'nom': f'{r.prestation.nom} : {float(r.valeur):g} {r.prestation.unite} / j'}
                                  for r in options_rendements.values()], key=lambda x: x['nom']),
            'descriptions': [{'id': d.id, 'nom': d.nom, 'detail': next((p.nom for p in projets if p.id == d.projet_id), '')}
                             for d in options_descriptions],
            'statuts': [{'id': s.id, 'nom': s.nom} for s in Statut.objects.order_by('ordre', 'id')],
        },
    }


class DureeEstimativeView(APIView):
    def get(self, request):
        verifier(request.user, MODULE, 'voir')
        return Response(calculer(request.user, request.query_params))


class ExportDureeEstimativeView(APIView):
    def get(self, request):
        from ikarama.vues import reponse_excel
        verifier(request.user, MODULE, 'exporter')
        donnees = calculer(request.user, request.query_params, 'exporter')
        try:
            ressources = {str(k): max(1, int(v)) for k, v in json.loads(request.query_params.get('ressources') or '{}').items()}
        except (TypeError, ValueError):
            ressources = {}
        en_jours = request.query_params.get('unite', 'jours') != 'heures'
        h = donnees['heures_par_jour']
        unite = 'j' if en_jours else 'h'
        convertir = (lambda heures: round(heures / h, 2)) if en_jours else (lambda heures: round(heures, 2))
        colonnes = [{'cle': c, 'libelle': l} for c, l in (
            ('affaire', 'Affaire'), ('prestation', 'Prestation'), ('nom', 'Projet / Commune'), ('quantite', 'Quantité'),
            ('quantite_restante', 'Quantité restante'), ('rendement_objectif', 'Rendement objectif / j'),
            ('ressources', 'Ressources disponibles'), ('duree', f'Durée totale ({unite})'), ('duree_restante', f'Durée restante ({unite})'))]
        lignes = []
        for p in donnees['projets']:
            n = ressources.get(str(p['id']), 1)
            lignes.append({**p, 'ressources': n,
                           'duree': convertir(p['temps_heures'] / n) if p['temps_heures'] is not None else None,
                           'duree_restante': convertir(p['temps_restant_heures'] / n) if p['temps_restant_heures'] is not None else None})
        return reponse_excel('Duree estimatif', colonnes, lignes)
