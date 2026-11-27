# backend/autorisations/acces.py
"""
Accès au site : SOURCE UNIQUE de vérité.

  a_acces(employe)        -> la personne peut-elle entrer sur le site ?
  q_visible(prefixe)      -> filtre Django des personnes visibles dans l'application :
                             celles qui ont accès + celles qui se sont déjà connectées
                             (même si leur accès a été retiré depuis).
  expliquer(employe)      -> pourquoi la personne a (ou n'a pas) accès (page Paramètres).

Le résultat est calculé pour tous les employés en une fois, puis gardé en cache
(60 s au plus) ; il est recalculé dès qu'une règle ou une fiche employé change.
"""
import time

from django.core.cache import cache
from django.db.models import Q

from utilisateurs.models import Employe

CLE_VERSION = 'acces_site_version'
DUREE_CACHE = 60


def invalider():
    """À appeler quand une règle ou une fiche employé change (voir signals.py)."""
    cache.set(CLE_VERSION, time.time_ns(), None)


def _regles():
    from .models import RegleAcces
    return list(RegleAcces.objects.filter(actif=True).select_related('employe'))


def q_regle(regle):
    """Filtre Django des employés concernés par UNE règle."""
    from .intitules import q_intitule   # comparaison tolérante (majuscules, accents, espaces)
    if regle.critere == 'POLE':
        return q_intitule('pole', [regle.pole])
    if regle.critere == 'POSTE':
        return q_intitule('poste_nom', [regle.poste])
    if regle.critere == 'MATRICULE':
        return Q(pk=regle.employe_id)
    if regle.critere == 'N1':
        if regle.portee == 'HIERARCHIE' and regle.employe:
            return Q(pk__in=[e.pk for e in regle.employe.subordonnes_hierarchie()])
        return Q(chef_id=regle.employe_id)
    return Q(pk__in=[])


def _ids_correspondants(regles):
    if not regles:
        return set()
    q = Q()
    for regle in regles:
        q |= q_regle(regle)
    return set(Employe.objects.filter(q).values_list('pk', flat=True).distinct())


def _calculer():
    regles = _regles()
    autorisations = [r for r in regles if r.effet == 'AUTORISER']
    refus = _ids_correspondants([r for r in regles if r.effet == 'REFUSER'])
    if not autorisations:
        # Mode ouvert : tout le monde, sauf les refus
        return {'ouvert': True, 'refuses': refus, 'autorises': set()}
    return {'ouvert': False, 'refuses': refus, 'autorises': _ids_correspondants(autorisations) - refus}


def etat():
    version = cache.get(CLE_VERSION)
    if version is None:
        invalider()
        version = cache.get(CLE_VERSION)
    cle = f'acces_site_{version}'
    resultat = cache.get(cle)
    if resultat is None:
        resultat = _calculer()
        cache.set(cle, resultat, DUREE_CACHE)
    return resultat


def a_acces_id(employe_id):
    e = etat()
    if employe_id in e['refuses']:
        return False
    return True if e['ouvert'] else employe_id in e['autorises']


def a_acces(employe):
    return bool(employe) and a_acces_id(employe.pk)


def q_visible(prefixe=''):
    """
    Filtre des personnes visibles. `prefixe` sert pour une relation, ex. 'subordonnes__'.
        Employe.objects.filter(q_visible())
        Employe.objects.annotate(n=Count('subordonnes', filter=q_visible('subordonnes__')))
    """
    e = etat()
    deja_connecte = Q(**{f'{prefixe}premiere_connexion__isnull': False})
    if e['ouvert']:
        return ~Q(**{f'{prefixe}pk__in': e['refuses']}) | deja_connecte if e['refuses'] else Q()
    return Q(**{f'{prefixe}pk__in': e['autorises']}) | deja_connecte


def est_visible(employe):
    """La personne peut-elle apparaître dans l'application ? (accès actuel, ou déjà connectée)"""
    return bool(employe) and (a_acces_id(employe.pk) or employe.premiere_connexion is not None)


def q_acces(prefixe=''):
    """Filtre des personnes qui ont accès au site en ce moment (sans celles qui l'ont perdu)."""
    e = etat()
    if e['ouvert']:
        return ~Q(**{f'{prefixe}pk__in': e['refuses']}) if e['refuses'] else Q()
    return Q(**{f'{prefixe}pk__in': e['autorises']})


def employes_visibles():
    return Employe.objects.filter(q_visible())


def filtre_ou_rien(prefixe=''):
    """Comme q_visible(), mais None quand tout le monde est visible (pratique pour Count(filter=...))."""
    q = q_visible(prefixe)
    return q if q.children else None


def statut(employe):
    """CONNECTE (accès + déjà connecté) | AUTORISE (accès, jamais connecté) | RETIRE (accès retiré)."""
    if a_acces(employe):
        return 'CONNECTE' if employe.premiere_connexion else 'AUTORISE'
    return 'RETIRE' if employe.premiere_connexion else 'REFUSE'


def responsable_visible(employe_id, chefs, visibles):
    """Premier responsable visible au-dessus d'une personne (en sautant les personnes masquées)."""
    vus, courant = {employe_id}, chefs.get(employe_id)
    while courant is not None and courant not in vus:
        if courant in visibles:
            return courant
        vus.add(courant)
        courant = chefs.get(courant)
    return None


def expliquer(employe):
    """Liste des règles qui concernent la personne, et la décision finale."""
    regles = _regles()
    concernees = [r for r in regles if Employe.objects.filter(pk=employe.pk).filter(q_regle(r)).exists()]
    ouvert = not any(r.effet == 'AUTORISER' for r in regles)
    return {
        'acces': a_acces(employe),
        'mode_ouvert': ouvert,
        'regles': [{'id': r.id, 'effet': r.effet, 'description': r.description()} for r in concernees],
    }
