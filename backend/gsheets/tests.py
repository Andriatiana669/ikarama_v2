# backend/gsheets/tests.py
"""Lancer : python manage.py test gsheets"""
from decimal import Decimal
from django.test import TestCase

from authentification.tests import AuthentifieMixin
from marches.models import Affaire, AffairePrestation, Description, Prestation, Projet, RendementObjectif, Statut
from rest_framework.test import APIClient
from utilisateurs.models import Employe

from .models import Feuille, HistoriqueLigne, LigneFeuille


class DonneesFeuilleMixin:
    """Données communes : une affaire (moi responsable, Tiana membre), un projet, deux descriptions."""

    def setUp(self):
        super().setUp()
        self.client.get('/api/auth/moi/')
        self.moi = Employe.objects.get(code_barre='PR00001')
        self.membre = Employe.objects.create(code_barre='PR2', nom='Rabe', prenom='Tiana', prenom_usuel='Tiana')
        self.etranger = Employe.objects.create(code_barre='PR3', nom='Rakoto', prenom='Mamy')
        self.prestation = Prestation.objects.create(nom='Saisie', unite='fiches')
        rendement = RendementObjectif.objects.create(prestation=self.prestation, valeur=120)
        self.affaire = Affaire.objects.create(nom='Recensement', num_affaire='AF-01')
        self.affaire.responsables.set([self.moi])
        self.affaire.membres.set([self.membre])
        AffairePrestation.objects.create(affaire=self.affaire, prestation=self.prestation)
        self.projet = Projet.objects.create(affaire=self.affaire, prestation=self.prestation, nom='Commune A',
                                            rendement=rendement, date_livraison='2026-12-31')
        self.d1 = Description.objects.create(projet=self.projet, nom='Ménages', quantite=100)
        self.d2 = Description.objects.create(projet=self.projet, nom='Établissements', quantite=40)
        self.statut = Statut.objects.create(nom='En cours', couleur='#E8EEF6')
        # Paramètres > Autorisation : sans droit de base, la gestion des feuilles passe par un rôle
        from autorisations.models import AttributionRole, DroitRole, Role
        # Rôle de test « Chef de projet » : feuilles et Marché de ses affaires, catalogues (pas Suivi ni Vérification)
        from autorisations.droits import MODULES
        role = Role.objects.create(nom='Chef de projet (tests)')
        for code, module in MODULES.items():
            if module['cible'] == 'personnes' or code == 'parametres_controles':
                continue
            perimetre = 'RESPONSABLE' if module['cible'] == 'affaires' else 'TOUS'
            for action in module['actions']:
                if not (code == 'gsheets_feuilles' and action == 'voir'):
                    DroitRole.objects.create(role=role, module=code, action=action, perimetre=perimetre)
        AttributionRole.objects.create(role=role, critere='MATRICULE', employe=self.moi)

    def creer(self, criteres=('Orthographe', 'Exhaustivité')):
        return self.client.post('/api/gsheets/feuilles/', {
            'nom': 'Suivi novembre',
            'perimetres_saisis': [{'affaire': self.affaire.id, 'prestation': self.prestation.id}],
            'criteres_saisis': list(criteres),
        })

    def lignes(self, feuille_id, client=None):
        return (client or self.client).get('/api/gsheets/lignes/', {'feuille': feuille_id}).data['results']

    def client_de(self, matricule):
        from authentification.tests import jeton_keycloak
        jeton = jeton_keycloak(matricule.lower())
        self.jetons_valides.add(jeton)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {jeton}')
        client.get('/api/auth/moi/')
        return client


class FeuillesTests(DonneesFeuilleMixin, AuthentifieMixin, TestCase):

    # --- Création ------------------------------------------------------
    def test_une_ligne_par_description(self):
        feuille = self.creer().data
        lignes = self.lignes(feuille['id'])
        self.assertEqual([l['marche']['description'] for l in lignes], ['Ménages', 'Établissements'])
        self.assertEqual(lignes[0]['marche']['quantite'], '100.00')
        self.assertEqual(lignes[0]['marche']['rendement_objectif'], '120.00')
        self.assertEqual(lignes[0]['avancement'], 0)
        self.assertEqual(len(feuille['criteres']), 2)

    def test_affaire_dont_je_ne_suis_pas_responsable_refusee(self):
        self.affaire.responsables.set([self.membre])
        self.assertEqual(self.creer().status_code, 400)                # affaire hors du périmètre du rôle (responsable)

    def test_commentaire_de_critere_obligatoire(self):
        self.assertEqual(self.creer(criteres=['Orthographe', ' ']).status_code, 400)

    def test_affaires_disponibles(self):
        donnees = self.client.get('/api/gsheets/feuilles/affaires-disponibles/').data
        self.assertEqual([(a['nom'], [p['nom'] for p in a['prestations']]) for a in donnees], [('Recensement', ['Saisie'])])

    # --- Suivi du Marché -----------------------------------------------
    def test_nouvelle_description_ajoutee_automatiquement(self):
        feuille = self.creer().data
        Description.objects.create(projet=self.projet, nom='Bâtiments', quantite=5)
        self.assertEqual([l['numero'] for l in self.lignes(feuille['id'])], [1, 2, 3])

    def test_description_sans_donnees_supprimee_avec_sa_ligne(self):
        feuille = self.creer().data
        reponse = self.client.delete(f'/api/marches/descriptions/{self.d1.id}/')
        self.assertEqual(reponse.status_code, 204)
        self.assertEqual([l['marche']['description'] for l in self.lignes(feuille['id'])], ['Établissements'])

    def test_description_avec_donnees_non_supprimable(self):
        feuille = self.creer().data
        ligne = self.lignes(feuille['id'])[0]
        self.client.patch(f"/api/gsheets/lignes/{ligne['id']}/", {'avancement': 10})
        reponse = self.client.delete(f'/api/marches/descriptions/{self.d1.id}/')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('Suivi novembre', reponse.data['detail'])
        self.assertIn('ligne 1', reponse.data['detail'])
        self.assertTrue(Description.objects.filter(pk=self.d1.pk).exists())
        self.assertEqual(len(self.lignes(feuille['id'])), 2)

    def test_statut_par_defaut_ne_compte_pas_comme_une_donnee(self):
        defaut = Statut.objects.create(nom='À faire', par_defaut=True)
        feuille = self.creer().data
        ligne = self.lignes(feuille['id'])[0]
        self.assertEqual(ligne['statut'], defaut.id)
        self.assertEqual(self.client.delete(f'/api/marches/descriptions/{self.d1.id}/').status_code, 204)

    def test_statut_change_compte_comme_une_donnee(self):
        Statut.objects.create(nom='À faire', par_defaut=True)
        feuille = self.creer().data
        ligne = self.lignes(feuille['id'])[0]
        self.client.patch(f"/api/gsheets/lignes/{ligne['id']}/", {'statut': self.statut.id})
        self.assertEqual(self.client.delete(f'/api/marches/descriptions/{self.d1.id}/').status_code, 400)

    def test_projet_avec_donnees_non_supprimable(self):
        feuille = self.creer().data
        ligne = self.lignes(feuille['id'])[1]
        self.client.patch(f"/api/gsheets/lignes/{ligne['id']}/", {'commentaires': 'en cours'})
        self.assertEqual(self.client.delete(f'/api/marches/projets/{self.projet.id}/').status_code, 400)
        self.assertEqual(Description.objects.filter(projet=self.projet).count(), 2)   # rien n'a été supprimé

    def test_projet_sans_donnees_supprimable(self):
        feuille = self.creer().data
        self.assertEqual(self.client.delete(f'/api/marches/projets/{self.projet.id}/').status_code, 204)
        self.assertEqual(self.lignes(feuille['id']), [])

    # --- Saisie ----------------------------------------------------------
    def test_saisie_par_le_responsable(self):
        feuille = self.creer().data
        ligne = self.lignes(feuille['id'])[0]
        critere = feuille['criteres'][0]['id']
        reponse = self.client.patch(f"/api/gsheets/lignes/{ligne['id']}/", {
            'employe': self.membre.id, 'statut': self.statut.id, 'avancement': 40, 'nb_reprises': 1,
            'notes_saisies': {str(critere): '4,5'}})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['employe_details']['identifiant'], 'PR2_Tiana')
        self.assertEqual(reponse.data['statut_details']['couleur'], '#E8EEF6')
        self.assertEqual(reponse.data['notes'][str(critere)], '4.50')

    def test_employe_hors_affaire_refuse(self):
        ligne = self.lignes(self.creer().data['id'])[0]
        self.assertEqual(self.client.patch(f"/api/gsheets/lignes/{ligne['id']}/", {'employe': self.etranger.id}).status_code, 400)

    def test_avancement_entre_0_et_100(self):
        ligne = self.lignes(self.creer().data['id'])[0]
        self.assertEqual(self.client.patch(f"/api/gsheets/lignes/{ligne['id']}/", {'avancement': 120}).status_code, 400)

    def test_droits_d_un_membre(self):
        feuille = self.creer().data
        l1, l2 = self.lignes(feuille['id'])
        critere = str(feuille['criteres'][0]['id'])
        client = self.client_de('PR2')
        self.assertEqual(len(self.lignes(feuille['id'], client)), 2)   # il voit la feuille
        # Sur toutes les lignes : employé, statut, avancement, commentaires, contrôleur, reprise
        for ligne in (l1, l2):
            reponse = client.patch(f"/api/gsheets/lignes/{ligne['id']}/", {
                'employe': self.membre.id, 'controleur': self.moi.id, 'employe_reprise': None,
                'statut': self.statut.id, 'avancement': 50, 'commentaires': 'ok'})
            self.assertEqual(reponse.status_code, 200, reponse.data)
        # Réservé aux responsables : reprises et critères
        self.assertEqual(client.patch(f"/api/gsheets/lignes/{l1['id']}/", {'nb_reprises': 1}).status_code, 400)
        self.assertEqual(client.patch(f"/api/gsheets/lignes/{l1['id']}/", {'notes_saisies': {critere: '3'}}).status_code, 400)
        self.assertEqual(self.client.patch(f"/api/gsheets/lignes/{l1['id']}/", {'nb_reprises': 1}).status_code, 200)

    def test_notes_de_critere_entre_1_et_5(self):
        feuille = self.creer().data
        ligne = self.lignes(feuille['id'])[0]
        critere = str(feuille['criteres'][0]['id'])
        url = f"/api/gsheets/lignes/{ligne['id']}/"
        self.assertEqual(self.client.patch(url, {'notes_saisies': {critere: '3,5'}}).status_code, 200)
        self.assertEqual(self.client.patch(url, {'notes_saisies': {critere: '6'}}).status_code, 400)
        self.assertEqual(self.client.patch(url, {'notes_saisies': {critere: '0,5'}}).status_code, 400)

    def test_statut_par_defaut_des_nouvelles_lignes(self):
        Statut.objects.create(nom='À faire', couleur='#FBF2E1', par_defaut=True)
        feuille = self.creer().data
        self.assertEqual({l['statut_details']['nom'] for l in self.lignes(feuille['id'])}, {'À faire'})

    def test_avancement_100_change_le_statut(self):
        termine = Statut.objects.create(nom='Terminé', avancement_complet=True)
        ligne = self.lignes(self.creer().data['id'])[0]
        reponse = self.client.patch(f"/api/gsheets/lignes/{ligne['id']}/", {'avancement': 100})
        self.assertEqual(reponse.data['statut'], termine.id)
        self.client.patch(f"/api/gsheets/lignes/{ligne['id']}/", {'avancement': 50})
        reponse = self.client.patch(f"/api/gsheets/lignes/{ligne['id']}/", {'avancement': 100, 'statut': self.statut.id})
        self.assertEqual(reponse.data['statut'], self.statut.id)   # un statut choisi en même temps l'emporte

    def test_note_de_rendement_quand_tout_le_projet_a_le_statut(self):
        valide = Statut.objects.create(nom='Validé', active_note_rendement=True)
        feuille = self.creer().data
        l1, l2 = LigneFeuille.objects.filter(feuille_id=feuille['id']).order_by('numero')
        LigneFeuille.objects.filter(pk__in=[l1.pk, l2.pk]).update(temps_prod=4)
        self.assertIsNone(self.lignes(feuille['id'])[0]['note_rendement'])
        self.client.patch(f'/api/gsheets/lignes/{l1.id}/', {'statut': valide.id})
        self.assertIsNone(self.lignes(feuille['id'])[0]['note_rendement'])          # l2 pas encore validée
        self.client.patch(f'/api/gsheets/lignes/{l2.id}/', {'statut': valide.id})
        self.assertIsNotNone(self.lignes(feuille['id'])[0]['note_rendement'])

    def test_note_de_rendement_sans_statut_configure(self):
        feuille = self.creer().data
        LigneFeuille.objects.filter(feuille_id=feuille['id']).update(temps_prod=4)
        self.assertIsNotNone(self.lignes(feuille['id'])[0]['note_rendement'])

    def test_un_seul_statut_par_defaut(self):
        a = Statut.objects.create(nom='A', par_defaut=True)
        Statut.objects.create(nom='B', par_defaut=True)
        a.refresh_from_db()
        self.assertFalse(a.par_defaut)

    # --- Calculs ----------------------------------------------------------
    def avec_temps(self, feuille_id, prod, controle=None, reprise=None):
        ligne = LigneFeuille.objects.filter(feuille_id=feuille_id).order_by('numero').first()   # Ménages : 100 fiches, objectif 120
        LigneFeuille.objects.filter(pk=ligne.pk).update(temps_prod=prod, temps_controle=controle, temps_reprise=reprise)
        return self.lignes(feuille_id)[0]

    def test_rendements_et_note_de_rendement(self):
        feuille = self.creer().data
        ligne = self.avec_temps(feuille['id'], prod=4, controle=1, reprise=1)
        self.assertEqual(ligne['rendement_prod'], '200.00')       # 100 / 4 × 8
        self.assertEqual(ligne['rendement_total'], '133.33')      # 100 / 6 × 8
        self.assertEqual(ligne['note_rendement'], '2.78')         # 2,5 × 133,33 / 120
        ligne = self.avec_temps(feuille['id'], prod=1)
        self.assertEqual(ligne['note_rendement'], '5.00')         # plafonnée à 5

    def test_colonnes_calculees_vides_sans_temps(self):
        ligne = self.lignes(self.creer().data['id'])[0]
        self.assertEqual((ligne['rendement_prod'], ligne['rendement_total'], ligne['note_rendement']), (None, None, None))

    def test_note_de_qualite_avec_criteres(self):
        feuille = self.creer(criteres=['A', 'B', 'C']).data
        ligne = self.lignes(feuille['id'])[0]
        ids = [str(c['id']) for c in feuille['criteres']]
        self.client.patch(f"/api/gsheets/lignes/{ligne['id']}/", {'notes_saisies': {ids[0]: '4', ids[1]: '3'}})
        self.assertEqual(self.lignes(feuille['id'])[0]['note_qualite'], '3.50')   # moyenne des critères remplis
        self.client.patch(f"/api/gsheets/lignes/{ligne['id']}/", {'notes_saisies': {ids[2]: '5'}})
        self.assertEqual(self.lignes(feuille['id'])[0]['note_qualite'], '4.00')

    def test_note_de_qualite_sans_critere(self):
        feuille = self.client.post('/api/gsheets/feuilles/', {
            'nom': 'Sans critère', 'utiliser_criteres': False,
            'perimetres_saisis': [{'affaire': self.affaire.id, 'prestation': self.prestation.id}]}).data
        self.assertFalse(feuille['utiliser_criteres'])
        # reprise sur 10 h de prod : 10 % -> 5 ; 15 % (limite) -> 4 ; 40 % -> 3 ; 60 % -> 2 ; 90 % -> 1
        attendus = [(1, '5.00'), (1.5, '4.00'), (4, '3.00'), (6, '2.00'), (9, '1.00')]
        for reprise, note in attendus:
            self.assertEqual(self.avec_temps(feuille['id'], prod=10, reprise=reprise)['note_qualite'], note, reprise)

    def test_parametres_modifiables(self):
        from django.contrib.auth.models import User
        User.objects.filter(username='PR00001').update(is_staff=True)
        reponse = self.client.put('/api/rendements/parametres/', {'heures_par_jour': '7'})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        feuille = self.creer().data
        self.assertEqual(self.avec_temps(feuille['id'], prod=4)['rendement_prod'], '175.00')   # 100 / 4 × 7
        mauvais = self.client.put('/api/rendements/parametres/', {'tranches_reprise': [{'jusqua': 50, 'note': 5}, {'jusqua': 20, 'note': 3}, {'jusqua': None, 'note': 1}]})
        self.assertEqual(mauvais.status_code, 400)

    def test_parametres_reserves_aux_administrateurs(self):
        self.assertEqual(self.client.get('/api/rendements/parametres/').status_code, 200)
        self.assertEqual(self.client.put('/api/rendements/parametres/', {'heures_par_jour': '7'}).status_code, 403)

    def test_mes_feuilles(self):
        self.creer()
        self.assertEqual(self.client_de('PR2').get('/api/gsheets/feuilles/').data['count'], 1)
        self.assertEqual(self.client_de('PR3').get('/api/gsheets/feuilles/').data['count'], 0)

    def test_modifier_les_criteres(self):
        feuille = self.creer().data
        reponse = self.client.patch(f"/api/gsheets/feuilles/{feuille['id']}/", {'criteres_saisis': ['Orthographe']})
        self.assertEqual([c['commentaire'] for c in reponse.data['criteres']], ['Orthographe'])

    def test_export_avec_notes(self):
        import json
        feuille = self.creer().data
        colonnes = json.dumps([{'cle': 'marche.description', 'libelle': 'Description'},
                               {'cle': f"notes.{feuille['criteres'][0]['id']}", 'libelle': 'Critère 1'}])
        reponse = self.client.get('/api/gsheets/lignes/exporter/', {'feuille': feuille['id'], 'colonnes': colonnes})
        self.assertEqual(reponse.status_code, 200)


class PlusieursFeuillesTests(AuthentifieMixin, TestCase):
    """Régression : chaque feuille n'affiche que ses propres lignes."""

    def test_une_feuille_n_affiche_que_ses_lignes(self):
        from django.contrib.auth.models import User
        self.client.get('/api/auth/moi/')
        User.objects.filter(username='PR00001').update(is_staff=True, is_superuser=True)   # crée les feuilles
        moi = Employe.objects.get(code_barre='PR00001')
        prestation = Prestation.objects.create(nom='P', unite='u')
        rendement = RendementObjectif.objects.create(prestation=prestation, valeur=1)
        feuilles = {}
        for nom in ('A', 'B'):
            affaire = Affaire.objects.create(nom=nom)
            affaire.responsables.set([moi])
            AffairePrestation.objects.create(affaire=affaire, prestation=prestation)
            projet = Projet.objects.create(affaire=affaire, prestation=prestation, nom=f'Projet {nom}',
                                           rendement=rendement, date_livraison='2026-12-31')
            Description.objects.create(projet=projet, nom=f'Description {nom}')
            feuilles[nom] = self.client.post('/api/gsheets/feuilles/', {
                'nom': nom, 'perimetres_saisis': [{'affaire': affaire.id, 'prestation': prestation.id}]}).data['id']
        for nom, identifiant in feuilles.items():
            lignes = self.client.get('/api/gsheets/lignes/', {'feuille': identifiant}).data['results']
            self.assertEqual([l['marche']['description'] for l in lignes], [f'Description {nom}'])


class SuiviEnDirectTests(DonneesFeuilleMixin, AuthentifieMixin, TestCase):
    """Suivi en direct, présence, conflits et historique."""

    def test_conflit_quand_quelqu_un_a_modifie_entre_temps(self):
        feuille = self.creer().data
        ligne = self.lignes(feuille['id'])[0]
        url = f"/api/gsheets/lignes/{ligne['id']}/"
        # Tiana (membre) passe l'avancement à 30 ; je voyais encore 0
        self.client_de('PR2').patch(url, {'avancement': 30, 'attendu': {'avancement': 0}})
        reponse = self.client.patch(url, {'avancement': 50, 'attendu': {'avancement': 0}}, format='json')
        self.assertEqual(reponse.status_code, 409)
        self.assertEqual(reponse.data['code'], 'conflit')
        self.assertIn('PR2', reponse.data['detail'])
        # Une autre case de la même ligne reste modifiable
        self.assertEqual(self.client.patch(url, {'commentaires': 'ok', 'attendu': {'commentaires': ''}}, format='json').status_code, 200)

    def test_remplacer_et_vider_une_liste_deroulante(self):
        feuille = self.creer().data
        ligne = self.lignes(feuille['id'])[0]
        url = f"/api/gsheets/lignes/{ligne['id']}/"
        envoyer = lambda donnees: self.client.patch(url, donnees, format='json')
        self.assertEqual(envoyer({'employe': self.membre.id, 'attendu': {'employe': None}}).status_code, 200)
        self.assertEqual(envoyer({'employe': self.moi.id, 'attendu': {'employe': self.membre.id}}).status_code, 200)   # remplacer
        self.assertEqual(envoyer({'employe': None, 'attendu': {'employe': self.moi.id}}).status_code, 200)            # vider
        self.assertEqual(envoyer({'statut': self.statut.id, 'attendu': {'statut': None}}).status_code, 200)
        self.assertEqual(envoyer({'statut': None, 'attendu': {'statut': self.statut.id}}).status_code, 200)
        ligne = self.lignes(feuille['id'])[0]
        self.assertEqual((ligne['employe'], ligne['statut']), (None, None))

    def test_conflit_dans_une_liste_deroulante(self):
        feuille = self.creer().data
        ligne = self.lignes(feuille['id'])[0]
        url = f"/api/gsheets/lignes/{ligne['id']}/"
        self.client_de('PR2').patch(url, {'controleur': self.membre.id})   # Tiana choisit le contrôleur
        reponse = self.client.patch(url, {'controleur': self.moi.id, 'attendu': {'controleur': None}}, format='json')
        self.assertEqual(reponse.status_code, 409)   # je voyais encore la case vide

    def test_historique_des_modifications(self):
        feuille = self.creer().data
        ligne = self.lignes(feuille['id'])[0]
        critere = feuille['criteres'][0]['id']
        url = f"/api/gsheets/lignes/{ligne['id']}/"
        self.client.patch(url, {'avancement': 40, 'employe': self.membre.id}, format='json')
        self.client.patch(url, {'avancement': 40, 'notes_saisies': {str(critere): '4'}}, format='json')   # avancement inchangé
        entrees = self.client.get('/api/gsheets/historique/', {'feuille': feuille['id'], 'ligne': ligne['id']}).data['results']
        resume = sorted((e['libelle'], e['ancienne_valeur'], e['nouvelle_valeur']) for e in entrees)
        self.assertEqual(resume, [('Avancement', '0', '40'), ('Critère 1', '', '4'), ('Employé', '', 'PR2_Tiana')])
        self.assertEqual(entrees[0]['auteur_details']['code_barre'], 'PR00001')

    def test_derniere_modification(self):
        feuille = self.creer().data
        ligne = self.lignes(feuille['id'])[0]
        self.client_de('PR2').patch(f"/api/gsheets/lignes/{ligne['id']}/", {'commentaires': 'vu'})
        self.assertEqual(self.lignes(feuille['id'])[0]['modifie_par_details']['code_barre'], 'PR2')

    def test_suivi_renvoie_les_changements_et_les_presences(self):
        feuille = self.creer().data
        ligne = self.lignes(feuille['id'])[0]
        premier = self.client.post('/api/gsheets/lignes/suivi/', {'feuille': feuille['id']}, format='json').data
        # Tiana commence à modifier l'avancement, puis enregistre
        tiana = self.client_de('PR2')
        tiana.post('/api/gsheets/lignes/suivi/', {'feuille': feuille['id'], 'edition': {'ligne': ligne['id'], 'champ': 'avancement'}}, format='json')
        tiana.patch(f"/api/gsheets/lignes/{ligne['id']}/", {'avancement': 70})
        suivi = self.client.post('/api/gsheets/lignes/suivi/', {'feuille': feuille['id'], 'depuis': premier['maintenant']}, format='json').data
        self.assertEqual([(l['id'], l['avancement']) for l in suivi['lignes']], [(ligne['id'], 70)])
        self.assertEqual([(p['ligne'], p['champ'], p['employe']['code_barre']) for p in suivi['presences']],
                         [(ligne['id'], 'avancement', 'PR2')])

    def test_suivi_refuse_hors_de_mes_feuilles(self):
        feuille = self.creer().data
        etranger = self.client_de('PR3')
        self.assertEqual(etranger.post('/api/gsheets/lignes/suivi/', {'feuille': feuille['id']}, format='json').status_code, 404)


class ImportFeuillesTests(DonneesFeuilleMixin, AuthentifieMixin, TestCase):
    """Import des feuilles et des données d'une feuille."""

    def fichier(self, lignes):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from openpyxl import Workbook
        classeur = Workbook()
        for ligne in lignes:
            classeur.active.append(ligne)
        flux = BytesIO()
        classeur.save(flux)
        return SimpleUploadedFile('import.xlsx', flux.getvalue())

    def importer(self, url, lignes, client=None):
        return (client or self.client).post(url, {'fichier': self.fichier(lignes)}, format='multipart').data

    def test_import_d_une_feuille_puis_mise_a_jour(self):
        entetes = ['Nom feuille', 'ID affaire', 'Prestation', 'Utiliser critères', 'Critères de CTRL']
        rapport = self.importer('/api/gsheets/feuilles/importer/', [entetes, ['Suivi importé', self.affaire.id, 'saisie', 'Oui', 'Orthographe; Délais']])
        self.assertEqual(rapport['crees'], 1, rapport)
        feuille = Feuille.objects.get(nom='Suivi importé')
        self.assertEqual([c.commentaire for c in feuille.criteres.all()], ['Orthographe', 'Délais'])
        self.assertEqual(feuille.lignes.count(), 2)
        rapport = self.importer('/api/gsheets/feuilles/importer/', [entetes, ['Suivi importé', self.affaire.id, 'Saisie', 'Non', None]])
        self.assertEqual(rapport['modifies'], 1)
        feuille.refresh_from_db()
        self.assertFalse(feuille.utiliser_criteres)
        self.assertEqual(feuille.criteres.count(), 2)          # critères vides : inchangés

    def test_import_feuille_prestation_non_cochee(self):
        rapport = self.importer('/api/gsheets/feuilles/importer/', [['Nom feuille', 'ID affaire', 'Prestation'], ['X', self.affaire.id, 'Inconnue']])
        self.assertEqual(rapport['erreurs'], 1)
        self.assertIn("n'est pas cochée", ' '.join(rapport['lignes'][0]['messages']))

    def test_modele_des_donnees_prerempli(self):
        from io import BytesIO

        from openpyxl import load_workbook
        feuille = self.creer().data
        reponse = self.client.get('/api/gsheets/lignes/modele/', {'feuille': feuille['id']})
        lignes = list(load_workbook(BytesIO(reponse.content)).active.values)
        self.assertEqual(lignes[0][:2], ('ID ligne *', 'Num affaire (info)'))
        self.assertEqual([l[0] for l in lignes[1:]], [1, 2])
        self.assertIn('Critère 1', lignes[0])

    def test_import_des_donnees_d_une_feuille(self):
        feuille = self.creer().data
        url = f"/api/gsheets/lignes/importer/?feuille={feuille['id']}"
        entetes = ['ID ligne', 'Description (info)', 'Employé', 'Statut', 'Avancement', 'Commentaires', 'Critère 1']
        rapport = self.importer(url, [entetes, [1, 'Ménages', 'PR2_Tiana', 'En cours', 0.4, 'Importé', 4.5],
                                      [2, 'Établissements', None, None, 0, '', None]])
        self.assertEqual((rapport['modifies'], rapport['inchanges'], rapport['erreurs']), (1, 1, 0), rapport)
        ligne = LigneFeuille.objects.get(feuille_id=feuille['id'], numero=1)
        self.assertEqual((ligne.employe_id, ligne.statut_id, ligne.avancement, ligne.commentaires),
                         (self.membre.id, self.statut.id, 40, 'Importé'))
        self.assertEqual(float(ligne.notes.get().note), 4.5)

    def test_import_des_donnees_par_un_membre(self):
        feuille = self.creer().data
        url = f"/api/gsheets/lignes/importer/?feuille={feuille['id']}"
        rapport = self.importer(url, [['ID ligne', 'Avancement', 'Nombre de reprises'], [1, 30, 2]], client=self.client_de('PR2'))
        # Données d'une feuille : règle métier, seuls le créateur et les responsables importent
        self.assertIn('responsables', rapport['detail'])


class SuiviMarcheTests(DonneesFeuilleMixin, AuthentifieMixin, TestCase):
    """Colonnes Temps et Statut du Marché, calculées depuis la feuille."""

    def setUp(self):
        super().setUp()
        self.termine = Statut.objects.create(nom='Terminé', couleur='#1E8A5A', active_note_rendement=True)
        feuille = self.creer().data
        self.l1, self.l2 = LigneFeuille.objects.filter(feuille_id=feuille['id']).order_by('numero')
        LigneFeuille.objects.filter(pk=self.l1.pk).update(temps_prod=4, temps_controle=1)
        LigneFeuille.objects.filter(pk=self.l2.pk).update(temps_prod=2, temps_reprise=Decimal('0.5'))

    def niveaux(self):
        a = self.affaire.id
        return {
            'descriptions': {d['nom']: (d['temps'], d['statut']) for d in self.client.get('/api/marches/descriptions/', {'projet': self.projet.id}).data['results']},
            'projet': next((p['temps'], p['statut']) for p in self.client.get('/api/marches/projets/', {'affaire': a, 'prestation': self.prestation.id}).data['results']),
            'prestation': next((p['temps'], p['statut']) for p in self.client.get('/api/marches/prestations/', {'affaire': a}).data['results'] if p['id'] == self.prestation.id),
            'affaire': next((x['temps'], x['statut']) for x in self.client.get('/api/marches/affaires/').data['results'] if x['id'] == a),
        }

    def test_temps_cumule_a_chaque_niveau(self):
        n = self.niveaux()
        self.assertEqual(n['descriptions']['Ménages'][0], '5.00')
        self.assertEqual(n['descriptions']['Établissements'][0], '2.50')
        self.assertEqual((n['projet'][0], n['prestation'][0], n['affaire'][0]), ('7.50', '7.50', '7.50'))

    def test_statut_en_cours_puis_final(self):
        self.client.patch(f'/api/gsheets/lignes/{self.l1.id}/', {'statut': self.termine.id})
        n = self.niveaux()
        self.assertEqual(n['descriptions']['Ménages'][1]['nom'], 'Terminé')
        self.assertEqual(n['projet'][1]['progression'], {'au_statut': 1, 'total': 2})
        self.client.patch(f'/api/gsheets/lignes/{self.l2.id}/', {'statut': self.termine.id})
        n = self.niveaux()
        for niveau in ('projet', 'prestation', 'affaire'):
            self.assertEqual((n[niveau][1]['nom'], n[niveau][1]['final']), ('Terminé', True), niveau)
        # Ligne rouverte : tout redescend
        self.client.patch(f'/api/gsheets/lignes/{self.l2.id}/', {'statut': self.statut.id})
        self.assertFalse(self.niveaux()['affaire'][1]['final'])

    def test_statut_commun(self):
        for ligne in (self.l1, self.l2):
            self.client.patch(f'/api/gsheets/lignes/{ligne.id}/', {'statut': self.statut.id})
        self.assertEqual(self.niveaux()['projet'][1]['nom'], 'En cours')


class TempsEstimatifTests(DonneesFeuilleMixin, AuthentifieMixin, TestCase):
    """Temps Estimatif = Quantité ÷ Rendement objectif × heures par jour ; couleur selon le Temps de prod."""

    def test_temps_estimatif_et_alertes(self):
        feuille = self.creer().data
        ligne = LigneFeuille.objects.get(feuille_id=feuille['id'], numero=1)        # Ménages : 100, objectif 120 / j
        lire = lambda: next(l for l in self.lignes(feuille['id']) if l['id'] == ligne.id)
        self.assertEqual((lire()['temps_estimatif'], lire()['alerte_temps']), ('6.67', None))   # 100 / 120 × 8
        LigneFeuille.objects.filter(pk=ligne.pk).update(temps_prod=Decimal('5.5'))   # ≥ 80 % (marge 20 %)
        self.assertEqual(lire()['alerte_temps'], 'orange')
        LigneFeuille.objects.filter(pk=ligne.pk).update(temps_prod=Decimal('7'))
        self.assertEqual(lire()['alerte_temps'], 'rouge')
        # Plus de couleur au statut qui active la note de rendement
        valide = Statut.objects.create(nom='Validé', active_note_rendement=True)
        LigneFeuille.objects.filter(pk=ligne.pk).update(statut=valide)
        self.assertIsNone(lire()['alerte_temps'])

    def test_parametres_temps_estimatif(self):
        self.assertEqual(self.client.get('/api/gsheets/temps-estimatif/').data['marge'], 20)
        self.assertEqual(self.client.put('/api/gsheets/temps-estimatif/', {'marge': 10}, format='json').status_code, 403)
        from django.contrib.auth.models import User
        User.objects.filter(username='PR00001').update(is_staff=True, is_superuser=True)
        reponse = self.client.put('/api/gsheets/temps-estimatif/', {'marge': 10, 'unite': 'jours', 'couleur_orange': '#ffaa00'}, format='json')
        self.assertEqual((reponse.status_code, reponse.data['couleur_orange'], reponse.data['unite']), (200, '#FFAA00', 'jours'))
        self.assertEqual(self.client.put('/api/gsheets/temps-estimatif/', {'marge': 150}, format='json').status_code, 400)


class ImportAncienTests(DonneesFeuilleMixin, AuthentifieMixin, TestCase):
    """Import des anciennes données : projets et descriptions créés, ligne remplie."""

    ENTETES = ['ID', 'Employé', 'Num affaire', 'Nom affaire', 'Prestation', 'Projet/Commune', 'Description', 'Unité',
               'Quantité', 'Temps de prod', 'Date de début', 'Statut', 'Commentaires', 'Contrôleur', 'Temps de contrôle',
               'Nombre de reprises', 'Date de livraison', 'Note de qualité', 'Critère 1', 'Critère 2']

    def importer(self, feuille_id, lignes, simulation=False):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from openpyxl import Workbook
        classeur = Workbook()
        classeur.active.append(self.ENTETES)
        for ligne in lignes:
            classeur.active.append(ligne)
        flux = BytesIO()
        classeur.save(flux)
        donnees = {'fichier': SimpleUploadedFile('ancien.xlsx', flux.getvalue())}
        if simulation:
            donnees['simulation'] = '1'
        return self.client.post(f'/api/gsheets/import-ancien/importer/?feuille={feuille_id}', donnees, format='multipart').data

    def test_import_ancien(self):
        from marches.models import Description, Projet
        feuille = self.creer().data
        lignes = [
            # projet existant, nouvelle description
            [12, 'PR2_Tiana', None, 'Recensement', 'Saisie', self.projet.nom, 'Écoles', 'fiches', 50, 7.5, '02/11/2026',
             'En cours', 'Ancien commentaire', 'PR00001', 1, 2, None, 3.5, 4, 5],
            # nouveau projet / commune
            [13, 'PR404', None, 'Recensement', 'saisie', 'Commune Nouvelle', 'Marchés', 'fiches', 30, 4, None,
             'Inconnu', '', None, None, 0, '31/12/2026', None, None, None],
            # affaire introuvable
            [14, None, 'X', 'Affaire absente', 'Saisie', 'P', 'D', '', 1, None, None, None, None, None, None, None, '01/01/2027', None, None, None],
        ]
        apercu = self.importer(feuille['id'], lignes, simulation=True)
        self.assertEqual((apercu['crees'], apercu['erreurs']), (2, 1), apercu)
        self.assertFalse(Projet.objects.filter(nom='Commune Nouvelle').exists())          # simulation : rien d'enregistré
        rapport = self.importer(feuille['id'], lignes)
        self.assertEqual((rapport['crees'], rapport['erreurs']), (2, 1), rapport)
        self.assertIn('introuvable', ' '.join(rapport['lignes'][1]['messages']))           # PR404 et statut inconnus
        ecoles = LigneFeuille.objects.get(feuille_id=feuille['id'], description__nom='Écoles')
        self.assertEqual((ecoles.employe_id, ecoles.controleur_id, str(ecoles.temps_prod), ecoles.nb_reprises, ecoles.commentaires),
                         (self.membre.id, self.moi.id, '7.50', 2, 'Ancien commentaire'))
        self.assertEqual(sorted(float(n.note) for n in ecoles.notes.all()), [4.0, 5.0])
        nouvelle = Description.objects.get(nom='Marchés')
        self.assertEqual((nouvelle.projet.nom, str(nouvelle.projet.date_livraison), float(nouvelle.quantite)), ('Commune Nouvelle', '2026-12-31', 30.0))
        self.assertTrue(LigneFeuille.objects.filter(feuille_id=feuille['id'], description=nouvelle).exists())

    def test_reimport_met_a_jour(self):
        feuille = self.creer().data
        ligne = [1, None, None, 'Recensement', 'Saisie', self.projet.nom, 'Ménages', '', 250, 3, None, None, 'Mis à jour', None, None, None, None, None, None, None]
        rapport = self.importer(feuille['id'], [ligne])
        self.assertEqual(rapport['modifies'], 1, rapport)                                  # description existante
        menages = LigneFeuille.objects.get(feuille_id=feuille['id'], description__nom='Ménages')
        self.assertEqual((float(menages.description.quantite), menages.commentaires), (250.0, 'Mis à jour'))

    def test_import_ancien_respecte_les_verrous(self):
        from marches.models import Tache
        from pointages.models import PartPointage, Pointage
        feuille = self.creer().data
        menages = LigneFeuille.objects.get(feuille_id=feuille['id'], description__nom='Ménages')
        LigneFeuille.objects.filter(pk=menages.pk).update(employe=self.moi)
        pointage = Pointage.objects.create(employe=self.moi, date='2026-11-02', heure_debut='08:00', heure_fin='09:00',
                                           tache=Tache.objects.create(nom='Saisie', type='PRODUCTION'))
        PartPointage.objects.create(pointage=pointage, description=menages.description, ligne=menages)
        rapport = self.importer(feuille['id'], [[1, 'PR2', None, 'Recensement', 'Saisie', self.projet.nom, 'Ménages', '', None,
                                                  9, None, None, None, None, None, None, None, None, None, None]])
        menages.refresh_from_db()
        self.assertEqual(menages.employe_id, self.moi.id)                                 # verrou respecté
        self.assertIn('verrouillé', ' '.join(rapport['lignes'][0]['messages']))
        self.assertIn('pointages', ' '.join(rapport['lignes'][0]['messages']))           # temps du fichier ignorés

    def test_import_ancien_reserve_aux_gestionnaires(self):
        feuille = self.creer().data
        from io import BytesIO
        reponse = self.client_de('PR2').get(f"/api/gsheets/import-ancien/modele/?feuille={feuille['id']}")
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(self.client.get(f"/api/gsheets/import-ancien/modele/?feuille={feuille['id']}").status_code, 200)
        self.assertIsNotNone(BytesIO)


class MesFeuillesEtProfilTests(DonneesFeuilleMixin, AuthentifieMixin, TestCase):
    """Statuts par feuille, équipe des affaires (bouton œil), résumé du profil."""

    def test_statuts_et_equipe(self):
        feuille = self.creer().data
        termine = Statut.objects.create(nom='Terminé', couleur='#1E8A5A')
        LigneFeuille.objects.filter(feuille_id=feuille['id'], numero=1).update(statut=termine)
        f = next(x for x in self.client.get('/api/gsheets/feuilles/').data['results'] if x['id'] == feuille['id'])
        self.assertEqual(sorted((s['nom'], s['nombre']) for s in f['statuts']), [('Sans statut', 1), ('Terminé', 1)])
        equipe = self.client.get(f"/api/gsheets/feuilles/{feuille['id']}/equipe/").data
        self.assertEqual([r['code_barre'] for r in equipe[0]['responsables']], ['PR00001'])
        self.assertIn('PR2', [m['code_barre'] for m in equipe[0]['membres']])

    def test_resume_du_profil(self):
        feuille = self.creer().data
        Feuille.objects.filter(pk=feuille['id']).update(utiliser_criteres=False)          # note de qualité d'après les reprises
        LigneFeuille.objects.filter(feuille_id=feuille['id']).update(employe=self.moi, temps_prod=Decimal('4'),
                                                                    temps_reprise=Decimal('0.4'))
        resume = self.client.get('/api/gsheets/mon-resume/').data
        self.assertEqual((resume['nb_lignes'], len(resume['groupes'])), (2, 1))
        groupe = resume['groupes'][0]
        self.assertEqual((groupe['prestation'], groupe['quantite']), ('Saisie', 140.0))
        self.assertIsNotNone(resume['note_rendement'])
        self.assertEqual(resume['note_qualite'], 5.0)                                     # reprise 10 % du temps de prod


class StatutControleTests(DonneesFeuilleMixin, AuthentifieMixin, TestCase):
    """Statut de contrôle : même liste de statuts, valeur à part, historisée et importable."""

    def test_statut_de_controle(self):
        feuille = self.creer().data
        ligne = LigneFeuille.objects.get(feuille_id=feuille['id'], numero=1)
        valide = Statut.objects.create(nom='Contrôlé', couleur='#1E8A5A')
        reponse = self.client.patch(f'/api/gsheets/lignes/{ligne.id}/', {'statut_controle': valide.id}, format='json')
        self.assertEqual((reponse.status_code, reponse.data['statut_controle_details']['nom']), (200, 'Contrôlé'))
        ligne.refresh_from_db()
        self.assertIsNone(ligne.statut_id)                                  # le Statut de la ligne ne change pas
        self.assertTrue(HistoriqueLigne.objects.filter(ligne=ligne, libelle='Statut de contrôle', nouvelle_valeur='Contrôlé').exists())
