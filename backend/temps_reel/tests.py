# backend/temps_reel/tests.py
"""Lancer : python manage.py test temps_reel"""
from unittest import mock

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.test import TransactionTestCase

from authentification.tests import AuthentifieMixin
from gsheets.models import LigneFeuille
from gsheets.tests import DonneesFeuilleMixin
from ikarama.asgi import application


class TempsReelTests(DonneesFeuilleMixin, AuthentifieMixin, TransactionTestCase):
    """WebSocket : authentification, abonnement à une feuille, événements diffusés."""

    def connecter(self):
        communicateur = WebsocketCommunicator(application, '/ws/', headers=[(b'host', b'localhost'), (b'origin', b'http://localhost')])
        return communicateur

    def test_authentification_et_evenements(self):
        feuille = self.creer().data
        utilisateur = User.objects.get(username='PR00001')

        async def scenario():
            ws = self.connecter()
            connecte, _ = await ws.connect()
            self.assertTrue(connecte)
            # Jeton refusé
            with mock.patch('authentification.services.identite_depuis_jeton', side_effect=Exception('invalide')):
                await ws.send_json_to({'type': 'authentifier', 'jeton': 'faux'})
                self.assertEqual((await ws.receive_json_from())['type'], 'erreur')
            await ws.disconnect()

            ws = self.connecter()
            await ws.connect()
            with mock.patch('authentification.services.identite_depuis_jeton', return_value={}), \
                 mock.patch('authentification.services.utilisateur_depuis_identite', return_value=utilisateur):
                await ws.send_json_to({'type': 'authentifier', 'jeton': 'bon'})
                self.assertEqual(await ws.receive_json_from(), {'type': 'pret'})
            await ws.send_json_to({'type': 'suivre_feuille', 'feuille': feuille['id']})
            await ws.receive_nothing(0.2)
            # Un événement diffusé au groupe de la feuille arrive au navigateur
            await get_channel_layer().group_send(f"feuille_{feuille['id']}", {'type': 'evenement', 'donnees': {'type': 'feuille', 'feuille': feuille['id']}})
            self.assertEqual(await ws.receive_json_from(), {'type': 'feuille', 'feuille': feuille['id']})
            # Notification personnelle
            await get_channel_layer().group_send(f'employe_{self.moi.pk}', {'type': 'evenement', 'donnees': {'type': 'notification'}})
            self.assertEqual(await ws.receive_json_from(), {'type': 'notification'})
            await ws.disconnect()

        async_to_sync(scenario)()

    def test_feuille_hors_d_acces(self):
        feuille = self.creer().data
        from utilisateurs.models import Employe
        etranger = Employe.objects.get(code_barre='PR3')
        utilisateur = User(username='etranger')

        async def scenario():
            ws = self.connecter()
            await ws.connect()
            with mock.patch('temps_reel.consumers.authentifier', new=mock.AsyncMock(return_value=(utilisateur, etranger))):
                await ws.send_json_to({'type': 'authentifier', 'jeton': 'bon'})
                await ws.receive_json_from()
            await ws.send_json_to({'type': 'suivre_feuille', 'feuille': feuille['id']})
            self.assertEqual((await ws.receive_json_from())['type'], 'erreur')
            await ws.disconnect()

        async_to_sync(scenario)()

    def test_diffusion_apres_enregistrement(self):
        feuille = self.creer().data
        with mock.patch('temps_reel.diffusion.diffuser') as diffuser:
            ligne = LigneFeuille.objects.filter(feuille_id=feuille['id']).first()
            ligne.save()
            self.assertTrue(any(appel.args[0] == f"feuille_{feuille['id']}" for appel in diffuser.call_args_list))


class PlanningTempsReelTests(DonneesFeuilleMixin, AuthentifieMixin, TransactionTestCase):
    def test_planification_diffusee(self):
        from datetime import date, timedelta

        from planning.models import AffectationPlanning
        with mock.patch('temps_reel.diffusion.diffuser') as diffuser:
            AffectationPlanning.objects.create(employe=self.moi, date=date.today() + timedelta(days=1), projet=self.projet)
            self.assertTrue(any(appel.args[0] == 'planning' for appel in diffuser.call_args_list))

    def test_abonnement_au_planning(self):
        utilisateur = User.objects.get(username='PR00001') if User.objects.filter(username='PR00001').exists() else None
        moi = self.moi

        async def scenario():
            ws = WebsocketCommunicator(application, '/ws/', headers=[(b'host', b'localhost'), (b'origin', b'http://localhost')])
            await ws.connect()
            with mock.patch('temps_reel.consumers.authentifier', new=mock.AsyncMock(return_value=(utilisateur, moi))):
                await ws.send_json_to({'type': 'authentifier', 'jeton': 'bon'})
                await ws.receive_json_from()
            await ws.send_json_to({'type': 'suivre_planning'})
            await ws.receive_nothing(0.2)
            await get_channel_layer().group_send('planning', {'type': 'evenement', 'donnees': {'type': 'planning'}})
            self.assertEqual(await ws.receive_json_from(), {'type': 'planning'})
            await ws.disconnect()

        async_to_sync(scenario)()


class DroitsTempsReelTests(DonneesFeuilleMixin, AuthentifieMixin, TransactionTestCase):
    def test_changement_de_role_diffuse(self):
        from autorisations.models import Role
        with mock.patch('temps_reel.diffusion.diffuser') as diffuser:
            Role.objects.create(nom='Nouveau rôle')
            self.assertTrue(any(appel.args[0] == 'droits' for appel in diffuser.call_args_list))
