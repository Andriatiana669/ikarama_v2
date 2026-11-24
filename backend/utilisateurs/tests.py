# backend/utilisateurs/tests.py
"""Lancer : python manage.py test utilisateurs"""
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from authentification.tests import AuthentifieMixin

from .models import Employe
from .services_rh import synchroniser_tous

DONNEES_RH = [
    {'id': 1, 'codeBarre': 'PR10', 'nom': 'Rakoto', 'prenom': 'Jean', 'prenomUsuel': 'Jeannot',
     'email': 'pr10@exemple.test', 'chef': None,
     'employePoste': {'poleID': 5, 'pole': 'INFORMATIQUE', 'poste': {'nom': 'Développeur', 'statut': 'CADRE'}}},
    {'id': 2, 'codeBarre': 'PR11', 'nom': 'Rabe', 'prenom': 'Marie', 'chef': 1,
     'employePoste': [{'poleID': 5, 'pole': 'INFORMATIQUE', 'poste': {'nom': 'Testeuse', 'statut': 'AGENT'}}]},
]


@override_settings(EXTERNAL_API_EMPLOYE_URL='')
class UtilisateursTests(AuthentifieMixin, TestCase):

    def setUp(self):
        super().setUp()

    @mock.patch('utilisateurs.services_rh.lire_employes_externes', return_value=DONNEES_RH)
    def test_synchronisation_complete(self, _):
        resume = synchroniser_tous()
        self.assertEqual(resume['crees'], 2)
        self.assertEqual(resume['chefs_lies'], 1)
        marie = Employe.objects.get(code_barre='PR11')
        self.assertEqual(marie.chef.code_barre, 'PR10')
        self.assertEqual(marie.postes.get().poste_nom, 'Testeuse')
        # 2e passage : rien de nouveau
        self.assertEqual(synchroniser_tous()['crees'], 0)

    @mock.patch('utilisateurs.services_rh.lire_employes_externes', return_value=DONNEES_RH)
    def test_liste_recherche_et_filtres(self, _):
        synchroniser_tous()
        self.assertEqual(self.client.get('/api/utilisateurs/', {'search': 'jeannot'}).data['count'], 1)
        self.assertEqual(self.client.get('/api/utilisateurs/', {'poste': 'Testeuse'}).data['count'], 1)
        filtres = self.client.get('/api/utilisateurs/valeurs-filtres/').data
        self.assertEqual(filtres['poles'], ['INFORMATIQUE'])
        jean = Employe.objects.get(code_barre='PR10')
        self.assertEqual(len(self.client.get(f'/api/utilisateurs/{jean.id}/subordonnes/').data), 1)

    def test_synchroniser_reserve_aux_administrateurs(self):
        self.assertEqual(self.client.post('/api/utilisateurs/synchroniser/').status_code, 403)
        self.client.get('/api/auth/moi/')
        User.objects.filter(username='PR00001').update(is_staff=True)
        with mock.patch('utilisateurs.views.synchroniser_tous', return_value={'total': 0}):
            self.assertEqual(self.client.post('/api/utilisateurs/synchroniser/').status_code, 200)


class SynchroOuvertureTests(AuthentifieMixin, TestCase):
    """Mise à jour de sa propre fiche quand on ouvre l'application."""

    def setUp(self):
        super().setUp()
        # Le fil d'exécution est remplacé par un appel direct, pour pouvoir vérifier le résultat
        patcheur = mock.patch('utilisateurs.services_rh.threading.Thread',
                              side_effect=lambda target, args, daemon: mock.Mock(start=lambda: target(*args)))
        patcheur.start()
        self.addCleanup(patcheur.stop)

    @override_settings(EXTERNAL_API_EMPLOYE_URL='http://api-rh.test', SYNC_CONNEXION_INTERVALLE_HEURES=0)
    @mock.patch('utilisateurs.services_rh.lire_employes_externes')
    def test_fiche_mise_a_jour_a_chaque_ouverture(self, lire):
        lire.return_value = [{'id': 7, 'codeBarre': 'PR00001', 'nom': 'Rakoto', 'prenom': 'Jean', 'prenomUsuel': 'Jeannot'}]
        self.client.get('/api/auth/moi/')
        employe = Employe.objects.get(code_barre='PR00001')
        self.assertEqual(employe.prenom_usuel, 'Jeannot')
        self.assertEqual(employe.identifiant, 'PR00001_Jeannot')

        lire.return_value[0]['prenomUsuel'] = 'Jeanjean'
        self.client.get('/api/auth/moi/')   # 2e ouverture : nouvelle mise à jour
        employe.refresh_from_db()
        self.assertEqual(employe.prenom_usuel, 'Jeanjean')

    @override_settings(EXTERNAL_API_EMPLOYE_URL='http://api-rh.test', SYNC_CONNEXION_INTERVALLE_HEURES=8)
    @mock.patch('utilisateurs.services_rh.lire_employes_externes', return_value=[])
    def test_intervalle_respecte(self, lire):
        self.client.get('/api/auth/moi/')
        self.client.get('/api/auth/moi/')
        self.assertEqual(lire.call_count, 1)
