# backend/planning/tests.py
"""Lancer : python manage.py test planning"""
from datetime import date, timedelta

from django.test import TestCase

from authentification.tests import AuthentifieMixin
from autorisations.models import AttributionRole, DroitRole, Role
from gsheets.models import LigneFeuille
from gsheets.tests import DonneesFeuilleMixin
from marches.models import Statut, Tache
from notifications.models import Notification

from .models import AffectationPlanning


class PlanningTests(DonneesFeuilleMixin, AuthentifieMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.tache = Tache.objects.create(nom='Saisie', type='PRODUCTION')
        self.feuille = self.creer().data
        self.lundi = date.today() - timedelta(days=date.today().weekday())
        self.demain = date.today() + timedelta(days=1)

    def donner_role(self, actions, perimetre='MEMBRES_AFFAIRES'):
        role = Role.objects.create(nom='Planificateur')
        for a in actions:
            DroitRole.objects.create(role=role, module='planning_projet', action=a, perimetre=perimetre)
        AttributionRole.objects.create(role=role, critere='MATRICULE', employe=self.moi)

    def test_par_defaut_seulement_soi(self):
        grille = self.client.get('/api/planning/semaine/', {'semaine': self.lundi.isoformat()}).data
        self.assertEqual([l['employe']['code_barre'] for l in grille['lignes']], ['PR00001'])
        self.assertFalse(grille['droits']['creer'])
        reponse = self.client.post('/api/planning/affectations/', {'employe': self.moi.id, 'date': self.demain, 'projet': self.projet.id})
        self.assertEqual(reponse.status_code, 403)                       # planifier : seulement par un rôle

    def test_equipe_pointages_planifie_et_en_cours(self):
        self.donner_role(['voir', 'creer', 'modifier', 'supprimer'])
        # Passé / aujourd'hui : un pointage de Tiana ; en cours : statut choisi sur sa ligne
        self.client_de('PR2').post('/api/pointages/', {
            'date': date.today().isoformat(), 'heure_debut': '07:30', 'heure_fin': '09:30',
            'descriptions': [self.d1.id], 'tache': self.tache.id}, format='json')
        en_cours = Statut.objects.create(nom='En cours de saisie', en_train_de_faire=True)   # rôle du statut
        LigneFeuille.objects.filter(description=self.d1).update(statut=en_cours, employe=self.membre)
        # Avenir : planifier Tiana demain
        reponse = self.client.post('/api/planning/affectations/', {'employe': self.membre.id, 'date': self.demain, 'projet': self.projet.id})
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertTrue(Notification.objects.filter(destinataire=self.membre, titre__startswith='Planifié').exists())
        self.assertEqual(self.client.post('/api/planning/affectations/', {'employe': self.membre.id, 'date': self.demain,
                                                                          'projet': self.projet.id}).status_code, 400)   # doublon
        hier = date.today() - timedelta(days=1)
        self.assertEqual(self.client.post('/api/planning/affectations/', {'employe': self.membre.id, 'date': hier,
                                                                          'projet': self.projet.id}).status_code, 400)   # passé
        grille = self.client.get('/api/planning/semaine/', {'debut': self.lundi.isoformat(), 'semaines': 2}).data
        self.assertEqual((len(grille['jours']), len(grille['semaines'])), (14, 2))       # plusieurs semaines d'un coup
        tiana = tiana_auj = next(l for l in grille['lignes'] if l['employe']['code_barre'] == 'PR2')
        self.assertEqual(tiana['chefs'], [])
        self.assertEqual(tiana['cases'][self.demain.isoformat()]['prevu'][0]['projet'], self.projet.nom)
        self.assertEqual(tiana_auj['cases'][date.today().isoformat()]['pointe'][0]['minutes'], 120)
        self.assertEqual(tiana['en_cours'][0]['description'], self.d1.nom)
        self.assertNotIn(self.demain.isoformat(), tiana['jours_libres'])
        # Déplacer puis retirer
        affectation = AffectationPlanning.objects.get()
        apres = self.demain + timedelta(days=1)
        self.assertEqual(self.client.patch(f'/api/planning/affectations/{affectation.id}/', {'date': apres},
                                           content_type='application/json').status_code, 200)
        self.assertEqual(self.client.delete(f'/api/planning/affectations/{affectation.id}/').status_code, 204)

    def test_hors_perimetre(self):
        self.donner_role(['voir', 'creer'], perimetre='MOI')
        reponse = self.client.post('/api/planning/affectations/', {'employe': self.membre.id, 'date': self.demain, 'projet': self.projet.id})
        self.assertEqual(reponse.status_code, 403)
        self.assertEqual(self.client.get('/api/planning/semaine/exporter/').status_code, 200)   # droit de base : son propre planning


class EcheancesTests(DonneesFeuilleMixin, AuthentifieMixin, TestCase):
    def test_etat_des_echeances(self):
        from .views import etat_echeances
        self.creer()
        aujourd_hui = date.today()
        self.projet.date_livraison = aujourd_hui - timedelta(days=1)
        self.projet.save()
        self.assertEqual(etat_echeances([self.projet])[self.projet.id]['etat'], 'retard')
        self.projet.date_livraison = aujourd_hui + timedelta(days=3)
        self.projet.save()
        self.assertEqual(etat_echeances([self.projet])[self.projet.id]['etat'], 'proche')
        LigneFeuille.objects.filter(description__projet=self.projet).update(avancement=100)
        self.assertEqual(etat_echeances([self.projet])[self.projet.id]['etat'], 'termine')
        lundi = aujourd_hui - timedelta(days=aujourd_hui.weekday())
        grille = self.client.get('/api/planning/semaine/', {'debut': lundi.isoformat(), 'semaines': 2}).data
        self.assertEqual(grille['echeances'][self.projet.date_livraison.isoformat()][0]['projet'], self.projet.nom)
