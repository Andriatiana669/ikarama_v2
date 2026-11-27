# backend/autorisations/intitules.py
"""
Comparaison tolérante des intitulés de postes et de pôles (fiches de l'API RH) : sans tenir compte des majuscules,
des accents, des apostrophes typographiques ni des espaces en trop. « Chef de Projet », « chef de projet » et
« Chef  de projet  » désignent le même poste.
"""
import re
import unicodedata

from django.db.models import Q


def normaliser(texte):
    if not texte:
        return ''
    texte = unicodedata.normalize('NFKD', str(texte))
    texte = ''.join(c for c in texte if not unicodedata.combining(c))
    texte = texte.replace('’', "'").replace('‘', "'").replace('`', "'")
    return re.sub(r'\s+', ' ', texte).strip().casefold()


def ids_par_intitule(champ, valeurs):
    """Ids des employés dont un poste a cet intitulé (champ 'pole' ou 'poste_nom'), en comparaison tolérante."""
    from utilisateurs.models import EmployePoste
    cibles = {normaliser(v) for v in valeurs if v}
    if not cibles:
        return []
    return list({e for e, v in EmployePoste.objects.exclude(**{f'{champ}__isnull': True}).values_list('employe_id', champ)
                 if normaliser(v) in cibles})


def q_intitule(champ, valeurs, prefixe=''):
    return Q(**{f'{prefixe}pk__in': ids_par_intitule(champ, valeurs)})
