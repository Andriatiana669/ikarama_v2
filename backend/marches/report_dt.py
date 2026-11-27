# backend/marches/report_dt.py
"""
Affaires « Report DT » : la Quantité d'une description est calculée.

  Linéaire total (ML) du projet = Σ quantités linéaires de ses descriptions
  Quantité = Quantité linéaire × Surface (m²) ÷ Linéaire total            (arrondie à 2 décimales)

Une Surface ou une Quantité linéaire vide (ou un Linéaire total nul) donne une Quantité vide : la donnée manquante
se voit (pas de Temps Estimatif, contrôle « Descriptions sans quantité ») au lieu d'une ancienne valeur fausse.
Modifier une seule quantité linéaire change le Linéaire total, donc la Quantité de toutes les descriptions du projet :
chaque Quantité modifiée est inscrite dans l'historique de sa feuille.
"""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

DEUX = Decimal('0.01')


def arrondir(valeur):
    """« 12,345 » ou 12.345 -> Decimal('12.35') ; vide -> None. Lève ValueError si ce n'est pas un nombre."""
    if valeur is None or str(valeur).strip() == '':
        return None
    try:
        nombre = Decimal(str(valeur).replace(',', '.').replace(' ', '').replace('\u202f', ''))
    except InvalidOperation:
        raise ValueError(f'« {valeur} » n’est pas un nombre.')
    if nombre < 0:
        raise ValueError('La valeur ne peut pas être négative.')
    return nombre.quantize(DEUX, rounding=ROUND_HALF_UP)


def lineaire_total(projet):
    return sum((d.quantite_lineaire for d in projet.descriptions.all() if d.quantite_lineaire is not None), Decimal(0))


def quantite_calculee(quantite_lineaire, surface, total):
    if quantite_lineaire is None or surface is None or not total:
        return None
    return (Decimal(quantite_lineaire) * Decimal(surface) / Decimal(total)).quantize(DEUX, rounding=ROUND_HALF_UP)


def recalculer(projet, auteur=None):
    """Recalcule la Quantité de toutes les descriptions d'un projet d'une affaire Report DT. Renvoie les descriptions changées."""
    if not projet.affaire.report_dt:
        return []
    from gsheets.services import historiser_quantite
    descriptions = list(projet.descriptions.all())
    total = sum((d.quantite_lineaire for d in descriptions if d.quantite_lineaire is not None), Decimal(0))
    changees = []
    for d in descriptions:
        nouvelle = quantite_calculee(d.quantite_lineaire, projet.surface_m2, total)
        if nouvelle != d.quantite:
            ancienne = d.quantite
            d.quantite = nouvelle
            d.save(update_fields=['quantite'])
            historiser_quantite(d, ancienne, nouvelle, auteur)
            changees.append(d)
    return changees
