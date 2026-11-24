# backend/rendements/calculs.py
"""Formules des feuilles. Toutes renvoient None quand une donnée nécessaire manque."""
from decimal import ROUND_HALF_UP, Decimal


def _d(valeur):
    if valeur in (None, ''):
        return None
    return valeur if isinstance(valeur, Decimal) else Decimal(str(valeur))


def arrondi(valeur, chiffres=2):
    if valeur is None:
        return None
    return valeur.quantize(Decimal(1).scaleb(-chiffres), rounding=ROUND_HALF_UP)


def rendement_prod(quantite, temps_prod, parametres):
    quantite, temps_prod = _d(quantite), _d(temps_prod)
    if quantite is None or not temps_prod:
        return None
    return arrondi(quantite / temps_prod * parametres.heures_par_jour)


def rendement_total(quantite, temps_prod, temps_controle, temps_reprise, parametres):
    quantite, temps_prod = _d(quantite), _d(temps_prod)
    if quantite is None or temps_prod is None:
        return None
    total = temps_prod + (_d(temps_controle) or 0) + (_d(temps_reprise) or 0)
    if not total:
        return None
    return arrondi(quantite / total * parametres.heures_par_jour)


def note_rendement(rendement_tot, rendement_objectif, parametres):
    rendement_tot, rendement_objectif = _d(rendement_tot), _d(rendement_objectif)
    if rendement_tot is None or not rendement_objectif:
        return None
    note = parametres.note_objectif * rendement_tot / rendement_objectif
    return arrondi(max(Decimal(0), min(parametres.note_max, note)))


def note_qualite_criteres(notes):
    """Moyenne des critères remplis."""
    valeurs = [_d(n) for n in notes if n is not None]
    if not valeurs:
        return None
    return arrondi(sum(valeurs) / len(valeurs))


def pourcentage_reprise(temps_prod, temps_reprise):
    temps_prod = _d(temps_prod)
    if not temps_prod:
        return None
    return (_d(temps_reprise) or Decimal(0)) / temps_prod * 100


def note_qualite_reprise(temps_prod, temps_reprise, parametres):
    """Note de la tranche correspondant au pourcentage Temps de reprise ÷ Temps de prod."""
    pourcentage = pourcentage_reprise(temps_prod, temps_reprise)
    if pourcentage is None:
        return None
    for tranche in parametres.tranches_reprise:
        if tranche.get('jusqua') is None or pourcentage < Decimal(str(tranche['jusqua'])):
            return arrondi(Decimal(str(tranche['note'])))
    return None
