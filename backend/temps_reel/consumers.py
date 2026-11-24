# backend/temps_reel/consumers.py
"""
WebSocket /ws/ — un seul canal par onglet du navigateur.

Messages reçus du navigateur (JSON) :
  {"type": "authentifier", "jeton": "<jeton Keycloak>"}   en premier (le jeton n'apparaît pas dans l'adresse)
  {"type": "suivre_feuille", "feuille": 3}                 recevoir les changements de cette feuille (si on y a accès)
  {"type": "quitter_feuille"}
  {"type": "suivre_planning"} / {"type": "quitter_planning"}   changements du Planning Projet
Messages envoyés : {"type": "pret"}, {"type": "feuille", "feuille": 3}, {"type": "presence", "feuille": 3},
                   {"type": "notification"}, {"type": "planning"}, {"type": "erreur", "message": "…"}.
Sans authentification valide dans les 10 secondes, la connexion est fermée.
"""
import asyncio

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .diffusion import GROUPE_PLANNING, groupe_employe, groupe_feuille


@database_sync_to_async
def authentifier(jeton):
    """Même contrôle que l'API : jeton valide, compte relié à une fiche, accès au site."""
    from authentification.services import identite_depuis_jeton, utilisateur_depuis_identite
    from autorisations.permissions import verifier_acces_site
    utilisateur = utilisateur_depuis_identite(identite_depuis_jeton(jeton))
    verifier_acces_site(utilisateur)
    return utilisateur, getattr(utilisateur, 'employe', None)


@database_sync_to_async
def peut_suivre(employe, feuille_id):
    from gsheets.services import feuilles_de
    return feuilles_de(employe).filter(pk=feuille_id).exists()


class TempsReelConsumer(AsyncJsonWebsocketConsumer):
    DELAI_AUTHENTIFICATION = 10

    async def connect(self):
        self.employe = None
        self.groupes = set()
        self.feuille = None
        await self.accept()
        self.attente = asyncio.create_task(self._fermer_si_anonyme())

    async def _fermer_si_anonyme(self):
        await asyncio.sleep(self.DELAI_AUTHENTIFICATION)
        if self.employe is None:
            await self.close(code=4401)

    async def disconnect(self, code):
        if getattr(self, 'attente', None):
            self.attente.cancel()
        for groupe in list(getattr(self, 'groupes', [])):
            await self.channel_layer.group_discard(groupe, self.channel_name)

    async def _rejoindre(self, groupe):
        await self.channel_layer.group_add(groupe, self.channel_name)
        self.groupes.add(groupe)

    async def _quitter(self, groupe):
        await self.channel_layer.group_discard(groupe, self.channel_name)
        self.groupes.discard(groupe)

    async def receive_json(self, contenu, **kwargs):
        type_ = contenu.get('type')
        if type_ == 'authentifier':
            try:
                _, self.employe = await authentifier(str(contenu.get('jeton') or ''))
            except Exception:
                await self.send_json({'type': 'erreur', 'message': 'Authentification refusée.'})
                await self.close(code=4403)
                return
            if self.employe is None:
                await self.close(code=4403)
                return
            await self._rejoindre(groupe_employe(self.employe.pk))
            await self.send_json({'type': 'pret'})
            return
        if self.employe is None:
            await self.send_json({'type': 'erreur', 'message': 'Authentifiez-vous d’abord.'})
            return
        if type_ == 'suivre_feuille':
            feuille_id = contenu.get('feuille')
            if self.feuille:
                await self._quitter(groupe_feuille(self.feuille))
                self.feuille = None
            if str(feuille_id).isdigit() and await peut_suivre(self.employe, int(feuille_id)):
                self.feuille = int(feuille_id)
                await self._rejoindre(groupe_feuille(self.feuille))
            else:
                await self.send_json({'type': 'erreur', 'message': 'Feuille introuvable.'})
        elif type_ == 'quitter_feuille' and self.feuille:
            await self._quitter(groupe_feuille(self.feuille))
            self.feuille = None
        elif type_ == 'suivre_planning':
            # Simple signal : la page relit le planning avec ses propres droits
            await self._rejoindre(GROUPE_PLANNING)
        elif type_ == 'quitter_planning':
            await self._quitter(GROUPE_PLANNING)

    async def evenement(self, message):
        await self.send_json(message['donnees'])
