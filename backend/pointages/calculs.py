# backend/pointages/calculs.py
"""
Calcul de H_Durée et HS d'un pointage (en minutes).

Règles :
  - jours ouvrables (lundi à vendredi) :
      * H_Durée = temps entre 07h30 et 16h30 ;
      * HS      = temps avant 07h30 et après 16h30 ;
  - samedi et dimanche : tout le temps compte en HS ;
  - pause : la personne coche « Pause (−1 h) » sur UN pointage de la journée (obligatoire les jours
    ouvrables pointés, sinon c'est une erreur de pointage). L'heure est retirée de la H_Durée
    du pointage ; s'il en contient moins d'une heure, le reste est retiré des HS.
Chaque pointage se calcule seul : le résultat ne dépend pas des autres pointages de la journée.

  Avec la pause cochée :  08:00 → 16:30 : 7,5 h     09:00 → 16:30 : 6,5 h     07:30 → 16:30 : 8 h
"""
from datetime import time

DEBUT_JOURNEE = time(7, 30)
FIN_JOURNEE = time(16, 30)
DUREE_PAUSE = 60
MAX_NORMALES = 8 * 60   # journée complète (sert au « Manque » de la Vérification)


def minutes(t):
    return t.hour * 60 + t.minute


def chevauchement(a_debut, a_fin, b_debut, b_fin):
    return max(0, min(a_fin, b_fin) - max(a_debut, b_debut))


def est_ouvrable(jour):
    return jour.weekday() < 5


def calculer(jour, heure_debut, heure_fin, pause=False):
    """(minutes_normales, minutes_hs) d'un pointage."""
    d, f = minutes(heure_debut), minutes(heure_fin)
    total = f - d
    normales = chevauchement(d, f, minutes(DEBUT_JOURNEE), minutes(FIN_JOURNEE)) if est_ouvrable(jour) else 0
    hs = total - normales
    if pause:
        retrait = min(DUREE_PAUSE, normales)
        normales -= retrait
        hs -= min(DUREE_PAUSE - retrait, hs)
    return normales, hs


def repartir_journee(jour, pointages):
    """{id(objet): (minutes_normales, minutes_hs)} pour les pointages d'une journée."""
    return {id(p): calculer(jour, p.heure_debut, p.heure_fin, getattr(p, 'pause', False)) for p in pointages}


def creneaux_libres(intervalles, debut=DEBUT_JOURNEE, fin=FIN_JOURNEE):
    """
    Créneaux non pointés entre `debut` et `fin` (en minutes) : [(debut, fin), ...].
    intervalles = [(minutes_debut, minutes_fin), ...] des pointages de la journée.
    """
    libres, curseur, borne = [], minutes(debut), minutes(fin)
    for d, f in sorted(intervalles):
        if d > curseur:
            libres.append((curseur, min(d, borne)))
        curseur = max(curseur, f)
        if curseur >= borne:
            break
    if curseur < borne:
        libres.append((curseur, borne))
    return [(d, f) for d, f in libres if f > d]


def suggestion(intervalles):
    """
    Heures proposées pour un nouveau pointage : le premier créneau libre de 07h30–16h30,
    sinon (journée complète) à partir de la fin du dernier pointage.
    """
    libres = creneaux_libres(intervalles)
    if libres:
        return libres[0]
    fin_dernier = max((f for _, f in intervalles), default=minutes(FIN_JOURNEE))
    return fin_dernier, None
