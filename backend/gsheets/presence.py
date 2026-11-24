# backend/gsheets/presence.py
"""
Qui est en train de modifier quelle case d'une feuille.

Chaque navigateur ouvert sur une feuille envoie, toutes les quelques secondes (suivi en direct),
la case qu'il est en train de modifier. On garde ces informations en cache quelques secondes :
une personne qui ferme sa page disparaît d'elle-même. Rien n'est bloqué : c'est un simple affichage.
"""
import time

from django.core.cache import cache

DUREE_PRESENCE = 35   # secondes sans nouvelles avant de disparaître (les pages en temps réel la renouvellent toutes les 15 s)


def _cle(feuille_id):
    return f'presence_feuille_{feuille_id}'


def signaler(feuille_id, employe, ligne_id=None, champ=None):
    """
    Enregistre la case modifiée par la personne (ou rien si elle ne modifie rien).
    Renvoie True si sa présence a changé (autre case, arrivée, départ) : les autres en sont alors avertis.
    """
    if employe is None:
        return False
    maintenant = time.time()
    presences = {k: v for k, v in (cache.get(_cle(feuille_id)) or {}).items() if v['jusqua'] > maintenant}
    avant = presences.get(str(employe.pk))
    avant = (avant['ligne'], avant['champ']) if avant else None
    if ligne_id:
        presences[str(employe.pk)] = {
            'ligne': int(ligne_id), 'champ': str(champ or '')[:50], 'jusqua': maintenant + DUREE_PRESENCE,
            'employe': {'id': employe.pk, 'nom_affiche': employe.nom_affiche, 'identifiant': employe.identifiant,
                        'code_barre': employe.code_barre},
        }
    else:
        presences.pop(str(employe.pk), None)
    cache.set(_cle(feuille_id), presences, DUREE_PRESENCE * 2)
    apres = presences.get(str(employe.pk))
    return avant != ((apres['ligne'], apres['champ']) if apres else None)


def lire(feuille_id, sauf=None):
    """Présences en cours, sans la personne `sauf` (soi-même)."""
    maintenant = time.time()
    return [
        {'ligne': v['ligne'], 'champ': v['champ'], 'employe': v['employe']}
        for k, v in (cache.get(_cle(feuille_id)) or {}).items()
        if v['jusqua'] > maintenant and (sauf is None or k != str(sauf.pk))
    ]
