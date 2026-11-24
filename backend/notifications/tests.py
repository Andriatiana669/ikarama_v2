# backend/notifications/tests.py
"""Lancer : python manage.py test notifications"""
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings

from authentification.tests import AuthentifieMixin
from gsheets.models import LigneFeuille
from gsheets.tests import DonneesFeuilleMixin
from marches.models import Tache

from .models import Notification


class NotificationsTests(DonneesFeuilleMixin, AuthentifieMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.production = Tache.objects.create(nom='Saisie', type='PRODUCTION')
        self.feuille = self.creer().data
        self.ligne = LigneFeuille.objects.get(feuille_id=self.feuille['id'], numero=1)   # Ménages : 100, objectif 120 -> 6,67 h
        self.jour = date.today() - timedelta(days=(date.today().weekday() + 7))           # lundi de la semaine dernière

    def pointer(self, debut, fin, jour=None, client=None, pause=False):
        return (client or self.client).post('/api/pointages/', {
            'date': (jour or self.jour).isoformat(), 'heure_debut': debut, 'heure_fin': fin, 'pause': pause,
            'descriptions': [self.ligne.description_id], 'tache': self.production.id}, format='json')

    def test_ajout_a_une_affaire(self):
        Notification.objects.all().delete()
        from utilisateurs.models import Employe
        nouveau = Employe.objects.create(code_barre='PR9', nom='Nouveau', prenom='Nina')
        self.affaire.membres.add(nouveau)
        self.assertTrue(Notification.objects.filter(destinataire=nouveau, type='affaire').exists())

    def test_temps_estimatif_depasse(self):
        self.pointer('07:30', '13:30')                                   # 6 h ≥ 80 % de 6,67 h -> orange
        self.assertTrue(Notification.objects.filter(destinataire=self.moi, type='temps_estimatif', cle__endswith='orange').exists())
        self.pointer('13:30', '15:30')                                   # 8 h -> rouge
        self.assertTrue(Notification.objects.filter(destinataire=self.moi, type='temps_estimatif', cle__endswith='rouge').exists())
        # API : liste, compte, lecture
        self.assertGreaterEqual(self.client.get('/api/notifications/compte/').data['non_lues'], 2)
        premiere = self.client.get('/api/notifications/').data['results'][0]
        self.client.post(f"/api/notifications/{premiere['id']}/lire/")
        self.assertTrue(Notification.objects.get(pk=premiere['id']).lu)
        self.assertEqual(self.client.post('/api/notifications/tout-lire/').data['non_lues'], 0)

    def test_pointage_modifie_par_un_administrateur(self):
        p = self.pointer('08:00', '09:00', client=self.client_de('PR2')).data
        User.objects.filter(username='PR00001').update(is_staff=True, is_superuser=True)
        self.client.delete(f"/api/pointages/tous/{p['id']}/")
        self.assertTrue(Notification.objects.filter(destinataire=self.membre, type='pointage_modifie').exists())

    def test_rappels_et_recapitulatif(self):
        mardi = self.jour + timedelta(days=1)
        self.pointer('07:30', '12:00', jour=self.jour)                    # lundi incomplet, sans pause
        sortie = StringIO()
        call_command('envoyer_rappels', '--veille', '--date', mardi.isoformat(), '--simulation', stdout=sortie)
        self.assertIn('PR00001_Jean', sortie.getvalue())
        self.assertFalse(Notification.objects.filter(type='rappel_pointage').exists())   # simulation
        call_command('envoyer_rappels', '--veille', '--date', mardi.isoformat(), stdout=StringIO())
        call_command('envoyer_rappels', '--veille', '--date', mardi.isoformat(), stdout=StringIO())   # pas de doublon
        rappel = Notification.objects.get(destinataire=self.moi, type='rappel_pointage')
        self.assertIn('pause non cochée', rappel.message)
        call_command('envoyer_rappels', '--semaine', '--date', (self.jour + timedelta(days=4)).isoformat(), stdout=StringIO())
        self.assertEqual(Notification.objects.filter(destinataire=self.moi, type='rappel_pointage').count(), 2)

        self.moi.email = 'jean@exemple.mg'
        self.moi.save()
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            call_command('envoyer_recapitulatif', stdout=StringIO())
            self.assertEqual(len(mail.outbox), 1)
            self.assertIn('notification', mail.outbox[0].subject)
            call_command('envoyer_recapitulatif', stdout=StringIO())   # déjà envoyées : rien de plus
            self.assertEqual(len(mail.outbox), 1)

    def test_controles_et_accueil(self):
        self.assertEqual(self.client.get('/api/controles/').status_code, 403)
        LigneFeuille.objects.filter(pk=self.ligne.pk).update(temps_prod=Decimal('3'), employe=None)
        accueil = self.client.get('/api/accueil/').data
        self.assertIn('moi', accueil)
        self.assertNotIn('administrateur', accueil)
        self.assertEqual(accueil['responsable']['nb_affaires'], 1)                       # responsable de « Recensement »
        User.objects.filter(username='PR00001').update(is_staff=True, is_superuser=True)
        donnees = self.client.get('/api/controles/').data
        par_code = {c['code']: c for c in donnees['controles']}
        self.assertEqual(par_code['temps_sans_employe']['nombre'], 1)
        self.assertGreater(par_code['reglages']['nombre'], 0)
        self.assertIn('administrateur', self.client.get('/api/accueil/').data)


class CertificatsTests(DonneesFeuilleMixin, AuthentifieMixin, TestCase):
    def test_certificats_desactives_signales(self):
        from django.test import override_settings
        User.objects.filter(username='PR00001').update(is_staff=True, is_superuser=True)
        with override_settings(CA_BUNDLE=False):
            reglages = next(c for c in self.client.get('/api/controles/').data['controles'] if c['code'] == 'reglages')
            self.assertTrue(any('certificats HTTPS' in e['libelle'] for e in reglages['elements']))
        with override_settings(CA_BUNDLE=True):
            reglages = next(c for c in self.client.get('/api/controles/').data['controles'] if c['code'] == 'reglages')
            self.assertFalse(any('certificats HTTPS' in e['libelle'] for e in reglages['elements']))
