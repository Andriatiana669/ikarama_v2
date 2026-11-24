# backend/pointages/erreurs.py
"""
Erreurs de pointage d'une personne sur une période (Mon temps, rappels, page d'accueil) :
  INCOMPLET : jour ouvrable (jusqu'à « jusqu_a » compris) avec moins de 8 h pointées (H_Durée + HS) ;
  PAUSE     : jour ouvrable pointé sans la case « Pause (−1 h) ».
"""
from datetime import date as Date
from datetime import timedelta

from django.db.models import Sum

from .calculs import MAX_NORMALES, est_ouvrable
from .models import Pointage

JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']


def erreurs_pointage(employe, debut, fin, jusqu_a=None):
    aujourd_hui = Date.today()
    limite = min(fin, jusqu_a or aujourd_hui)
    pointages = Pointage.objects.filter(employe=employe, date__gte=debut, date__lte=fin).order_by()
    par_jour = {l['date']: (l['n'] or 0) + (l['h'] or 0)
                for l in pointages.values('date').annotate(n=Sum('minutes_normales'), h=Sum('minutes_hs'))}
    nom = lambda jour: "Aujourd'hui" if jour == aujourd_hui else f"{JOURS[jour.weekday()]} {jour:%d/%m}"

    erreurs = []
    jour = debut
    while jour <= limite:
        fait = par_jour.get(jour, 0)
        if est_ouvrable(jour) and fait < MAX_NORMALES:
            erreurs.append({'date': jour.isoformat(), 'type': 'INCOMPLET', 'minutes': fait,
                            'message': f"{nom(jour)} : {fait / 60:g} h pointée(s) sur 8 h".replace('.', ',')})
        jour += timedelta(days=1)
    avec_pause = set(pointages.filter(pause=True).values_list('date', flat=True))
    for jour in sorted(set(par_jour) - avec_pause):
        if est_ouvrable(jour) and jour <= limite:
            erreurs.append({'date': jour.isoformat(), 'type': 'PAUSE', 'minutes': par_jour[jour],
                            'message': f"{nom(jour)} : pause non cochée"})
    erreurs.sort(key=lambda e: (e['date'], e['type']))
    return erreurs
