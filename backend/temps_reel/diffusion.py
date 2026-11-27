# backend/temps_reel/diffusion.py
"""
Envoi d'événements aux navigateurs connectés (WebSocket). Les événements sont de simples signaux
(« la feuille 3 a changé », « nouvelle notification ») : le navigateur relit alors ce qui a changé par l'API,
avec ses propres droits. Si le temps réel est indisponible, rien ne casse (les pages interrogent aussi l'API).
"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

journal = logging.getLogger(__name__)


def groupe_feuille(feuille_id):
    return f'feuille_{feuille_id}'


def groupe_employe(employe_id):
    return f'employe_{employe_id}'


def diffuser(groupe, donnees):
    """Envoie l'événement après la validation de la transaction en cours (jamais pour une modification annulée)."""
    def envoyer():
        couche = get_channel_layer()
        if couche is None:
            return
        try:
            async_to_sync(couche.group_send)(groupe, {'type': 'evenement', 'donnees': donnees})
        except Exception:   # temps réel indisponible (Redis arrêté…) : les pages se rabattent sur l'API
            journal.warning('Temps réel indisponible : événement %s non diffusé', donnees.get('type'), exc_info=True)
    transaction.on_commit(envoyer)


def feuille_modifiee(feuille_id):
    diffuser(groupe_feuille(feuille_id), {'type': 'feuille', 'feuille': feuille_id})


def presence_modifiee(feuille_id):
    diffuser(groupe_feuille(feuille_id), {'type': 'presence', 'feuille': feuille_id})


GROUPE_PLANNING = 'planning'


def planning_modifie():
    """Le Planning Projet a changé (planification, pointage, statut d'une ligne) : les pages ouvertes se rafraîchissent."""
    diffuser(GROUPE_PLANNING, {'type': 'planning'})


GROUPE_DROITS = 'droits'


def droits_modifies():
    """Un rôle, un droit, une attribution ou une règle d'accès a changé : chaque page relit ses droits (/api/auth/moi/)."""
    diffuser(GROUPE_DROITS, {'type': 'droits'})


def nouvelle_notification(employe_id):
    diffuser(groupe_employe(employe_id), {'type': 'notification'})
