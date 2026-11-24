# backend/equipes/tests.py
"""Lancer : python manage.py test equipes"""
from django.test import TestCase

from authentification.tests import AuthentifieMixin
from utilisateurs.models import Employe, EmployePoste


def employe(code, nom, chef=None, pole='PRODUCTION', poste='Opérateur'):
    e = Employe.objects.create(code_barre=code, nom=nom, prenom=nom[:3], prenom_usuel=nom, chef=chef)
    EmployePoste.objects.create(employe=e, pole=pole, poste_nom=poste)
    return e


class EquipesTests(AuthentifieMixin, TestCase):
    """
    Hiérarchie de test :
        Alice (DSI) ── Bob (PRODUCTION) ── Dan
                    └─ PR00001 (moi)  ── Eve
    """

    def setUp(self):
        super().setUp()
        self.alice = employe('PR1', 'Alice', pole='DSI', poste='Directrice')
        self.bob = employe('PR2', 'Bob', chef=self.alice)
        self.moi = employe('PR00001', 'Moi', chef=self.alice)
        self.dan = employe('PR4', 'Dan', chef=self.bob)
        self.eve = employe('PR5', 'Eve', chef=self.moi)

    def test_une_equipe_par_responsable(self):
        donnees = self.client.get('/api/equipes/').data
        tailles = {e['responsable']['code_barre']: e['nb_membres'] for e in donnees['results']}
        self.assertEqual(tailles, {'PR1': 2, 'PR2': 1, 'PR00001': 1})

    def test_recherche_et_filtre_par_pole(self):
        self.assertEqual(self.client.get('/api/equipes/', {'search': 'alice'}).data['count'], 1)
        self.assertEqual(self.client.get('/api/equipes/', {'pole': 'PRODUCTION'}).data['count'], 2)

    def test_detail_avec_membres(self):
        detail = self.client.get(f'/api/equipes/{self.alice.id}/').data
        self.assertEqual([m['code_barre'] for m in detail['membres']], ['PR2', 'PR00001'])
        self.assertEqual(detail['membres'][0]['identifiant'], 'PR2_Bob')

    def test_pas_d_equipe_sans_collaborateur(self):
        self.assertEqual(self.client.get(f'/api/equipes/{self.dan.id}/').status_code, 404)

    def test_mes_equipes(self):
        roles = {e['responsable']['code_barre']: e['mon_role'] for e in self.client.get('/api/equipes/mes-equipes/').data}
        self.assertEqual(roles, {'PR00001': 'RESPONSABLE', 'PR1': 'MEMBRE'})

    def test_poles(self):
        poles = {p['pole']: (p['nb_employes'], p['nb_equipes']) for p in self.client.get('/api/equipes/poles/').data}
        self.assertEqual(poles, {'DSI': (1, 1), 'PRODUCTION': (4, 2)})

    def test_organigramme(self):
        arbre = self.client.get('/api/equipes/organigramme/').data
        self.assertEqual([r['code_barre'] for r in arbre], ['PR1'])
        self.assertEqual(sorted(e['code_barre'] for e in arbre[0]['enfants']), ['PR00001', 'PR2'])

    def test_organigramme_par_pole(self):
        arbre = self.client.get('/api/equipes/organigramme/', {'pole': 'PRODUCTION'}).data
        # Alice (DSI) est hors du pôle : Bob et moi deviennent des racines
        self.assertEqual(sorted(r['code_barre'] for r in arbre), ['PR00001', 'PR2'])

    def test_organigramme_resiste_a_une_boucle(self):
        Employe.objects.filter(pk=self.alice.pk).update(chef=self.dan)   # boucle Alice > Bob > Dan > Alice
        arbre = self.client.get('/api/equipes/organigramme/').data
        self.assertEqual(len(arbre), 1)
