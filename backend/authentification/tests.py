# backend/authentification/tests.py
"""
Lancer : python manage.py test authentification

Keycloak est simulé : `ClientKeycloakSimule` remplace l'appel à l'endpoint userinfo.
Les autres applications réutilisent `AuthentifieMixin` pour leurs tests.
"""
import time
from unittest import mock

import jwt
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from utilisateurs.models import Employe

KEYCLOAK_TEST = {
    'SERVER_URL': 'http://keycloak.test',
    'REALM': 'test',
    'CLIENT_ID': 'ikarama',
    'USERINFO_URL': 'http://keycloak.test/realms/test/protocol/openid-connect/userinfo',
}


def jeton_keycloak(utilisateur='pr00001', expire_dans=600, emetteur='http://keycloak.test/realms/test'):
    """Jeton au format Keycloak. Sa validité est décidée par le Keycloak simulé, pas par sa signature."""
    return jwt.encode({'iss': emetteur, 'sub': f'id-{utilisateur}', 'preferred_username': utilisateur,
                       'exp': int(time.time()) + expire_dans}, 'signature-sans-importance', algorithm='HS256')


class ReponseUserinfo:
    def __init__(self, statut, donnees=None):
        self.status_code, self._donnees = statut, donnees or {}

    def json(self):
        return self._donnees


def userinfo_simule(valides):
    """Fabrique un faux requests.get : 200 pour les jetons de `valides`, 401 sinon."""
    def faux_get(url, headers=None, **kwargs):
        jeton = headers['Authorization'].split(' ', 1)[1]
        if jeton not in valides:
            return ReponseUserinfo(401)
        nom = jwt.decode(jeton, options={'verify_signature': False})['preferred_username']
        return ReponseUserinfo(200, {'preferred_username': nom, 'sub': f'id-{nom}', 'email': f'{nom}@exemple.test',
                                     'given_name': 'Jean', 'family_name': 'Test'})
    return faux_get


class AuthentifieMixin:
    """À hériter dans les tests : self.client est connecté en tant que PR00001 (non administrateur)."""

    def setUp(self):
        super().setUp()
        reglages = override_settings(KEYCLOAK=KEYCLOAK_TEST)
        reglages.enable()
        self.addCleanup(reglages.disable)
        cache.clear()
        self.jeton = jeton_keycloak()
        self.jetons_valides = {self.jeton}
        patcheur = mock.patch('authentification.services.requests.get', side_effect=userinfo_simule(self.jetons_valides))
        patcheur.start()
        self.addCleanup(patcheur.stop)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.jeton}')


class AuthentificationTests(AuthentifieMixin, TestCase):

    def appeler_moi(self, jeton):
        return APIClient().get('/api/auth/moi/', HTTP_AUTHORIZATION=f'Bearer {jeton}')

    def test_sans_jeton_401(self):
        self.assertEqual(APIClient().get('/api/auth/moi/').status_code, 401)

    def test_jeton_valide_cree_compte_et_fiche(self):
        reponse = self.appeler_moi(self.jeton)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data['username'], 'PR00001')
        self.assertTrue(Employe.objects.filter(code_barre='PR00001', user__username='PR00001').exists())

    def test_jeton_existant_rattache_a_la_fiche(self):
        employe = Employe.objects.create(code_barre='PR00001', nom='Dupont', prenom='Jean')
        self.appeler_moi(self.jeton)
        employe.refresh_from_db()
        self.assertEqual(employe.user.username, 'PR00001')
        self.assertEqual(Employe.objects.count(), 1)

    def test_jeton_refuse_par_keycloak(self):
        # Un jeton fabriqué à la main : Keycloak ne le reconnaît pas
        self.assertEqual(self.appeler_moi(jeton_keycloak(utilisateur='admin')).status_code, 401)

    def test_jeton_hors_keycloak_refuse(self):
        jeton = jwt.encode({'id': 1, 'name': 'X', 'email': 'admin@x.test', 'exp': int(time.time()) + 600},
                           'cle-quelconque', algorithm='HS256')
        self.jetons_valides.add(jeton)   # même si un appel à Keycloak réussissait, il n'est pas tenté
        self.assertEqual(self.appeler_moi(jeton).status_code, 401)

    def test_jeton_illisible_refuse(self):
        self.assertEqual(self.appeler_moi('pas-un-jeton').status_code, 401)

    def test_compte_desactive_refuse(self):
        self.appeler_moi(self.jeton)
        User.objects.filter(username='PR00001').update(is_active=False)
        self.assertEqual(self.appeler_moi(self.jeton).status_code, 401)


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class EntreeAdminTests(AuthentifieMixin, TestCase):
    """Accès automatique à l'administration Django depuis l'application."""

    def devenir_admin(self):
        self.client.get('/api/auth/moi/')
        User.objects.filter(username='PR00001').update(is_staff=True, is_superuser=True)

    def test_ticket_refuse_aux_non_administrateurs(self):
        self.assertEqual(self.client.post('/api/auth/session-admin/').status_code, 403)

    def test_ticket_ouvre_la_session_admin_une_seule_fois(self):
        self.devenir_admin()
        url = self.client.post('/api/auth/session-admin/').data['url']

        navigateur = self.client_class()   # nouvel onglet : sans jeton, sans session
        reponse = navigateur.get(url)
        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(reponse['Location'], '/admin/')
        self.assertEqual(navigateur.get('/admin/').status_code, 200)   # connecté à l'admin

        # Le même ticket ne marche pas deux fois
        self.assertIn('/admin/login/', self.client_class().get(url)['Location'])

    def test_ticket_modifie_refuse(self):
        self.devenir_admin()
        url = self.client.post('/api/auth/session-admin/').data['url']
        self.assertIn('/admin/login/', self.client_class().get(url + 'x')['Location'])
