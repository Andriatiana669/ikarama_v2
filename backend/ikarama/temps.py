# backend/ikarama/temps.py
"""
La date et l'heure « d'aujourd'hui » pour tout le serveur, dans le fuseau du .env (TIME_ZONE, par défaut
Indian/Antananarivo), quel que soit le fuseau du système (une VM ou un serveur réglé en UTC, Windows…).
À utiliser à la place de date.today() / datetime.now().
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings


def maintenant():
    """Date et heure locales (sans fuseau, comme le reste de l'application : USE_TZ=False)."""
    return datetime.now(ZoneInfo(settings.TIME_ZONE)).replace(tzinfo=None)


def aujourdhui():
    return maintenant().date()
