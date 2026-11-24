from django.contrib.auth.models import User
# backend/marches/tests.py
"""Lancer : python manage.py test marches"""
import json

from django.test import TestCase

from authentification.tests import AuthentifieMixin
from utilisateurs.models import Employe

from .models import Affaire, Prestation, Projet


class MarcheTests(AuthentifieMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.client.get('/api/auth/moi/')
        self.moi = Employe.objects.get(code_barre='PR00001')
        # Ces tests préparent le Marché : superadmin (les droits par rôle sont testés dans autorisations)
        User.objects.filter(username='PR00001').update(is_staff=True, is_superuser=True)
        self.collegue = Employe.objects.create(code_barre='PR2', nom='Rabe', prenom='Tiana')
        self.prestation = self.client.post('/api/marches/prestations/', {
            'nom': 'Saisie', 'unite': 'fiches', 'valeurs_rendement': ['120', '80,5']}).data
        self.affaire = self.client.post('/api/marches/affaires/', {
            'nom': 'Recensement', 'num_affaire': 'AF-01',
            'responsables': [self.moi.id], 'membres': [self.moi.id, self.collegue.id]}).data

    def cocher(self, coche=True):
        return self.client.post(f"/api/marches/affaires/{self.affaire['id']}/prestations/",
                                {'prestation': self.prestation['id'], 'coche': coche})

    def creer_projet(self, nom='Commune A', **extra):
        return self.client.post('/api/marches/projets/', {
            'affaire': self.affaire['id'], 'prestation': self.prestation['id'], 'nom': nom,
            'quantite': '1000', 'rendement': self.prestation['rendements'][0]['id'],
            'date_livraison': '2026-12-31', **extra})

    # --- Catalogues --------------------------------------------------
    def test_prestation_et_rendements(self):
        self.assertEqual([r['valeur'] for r in self.prestation['rendements']], ['120.00', '80.50'])
        reponse = self.client.post('/api/marches/prestations/', {'nom': 'Vide', 'unite': 'pages'})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('valeurs_rendement', reponse.data['erreurs'])

    def test_rendement_utilise_non_retirable(self):
        self.cocher()
        self.creer_projet()
        reponse = self.client.patch(f"/api/marches/prestations/{self.prestation['id']}/", {'valeurs_rendement': ['80.5']})
        self.assertEqual(reponse.status_code, 400)

    # --- Affaires -----------------------------------------------------
    def test_affaire_creee_avec_auteur(self):
        self.assertEqual(self.affaire['cree_par_details']['code_barre'], 'PR00001')
        self.assertEqual(len(self.affaire['membres_details']), 2)

    def test_responsable_et_membre_obligatoires(self):
        reponse = self.client.post('/api/marches/affaires/', {'nom': 'X', 'responsables': [], 'membres': []})
        self.assertEqual(set(reponse.data['erreurs']), {'responsables', 'membres'})

    def test_num_affaire_facultatif_et_non_unique(self):
        base = {'responsables': [self.moi.id], 'membres': [self.moi.id]}
        self.assertEqual(self.client.post('/api/marches/affaires/', {'nom': 'B', 'num_affaire': 'AF-01', **base}).status_code, 201)
        self.assertEqual(self.client.post('/api/marches/affaires/', {'nom': 'C', **base}).status_code, 201)
        self.assertEqual(Affaire.objects.filter(num_affaire='AF-01').count(), 2)

    def test_prestations_cochees_en_premier(self):
        autre = self.client.post('/api/marches/prestations/', {'nom': 'Contrôle', 'unite': 'pages', 'valeurs_rendement': ['50']}).data
        self.client.post(f"/api/marches/affaires/{self.affaire['id']}/prestations/", {'prestation': autre['id']})
        noms = [p['nom'] for p in self.client.get(f"/api/marches/prestations/?affaire={self.affaire['id']}").data['results']]
        self.assertEqual(noms, ['Contrôle', 'Saisie'])            # cochée d'abord
        noms = [p['nom'] for p in self.client.get('/api/marches/prestations/').data['results']]
        self.assertEqual(noms, ['Saisie', 'Contrôle'])            # sans affaire : ordre du catalogue

    def test_suppression_definitive(self):
        url = f"/api/marches/affaires/{self.affaire['id']}/supprimer/"
        self.cocher()
        self.creer_projet()
        reponse = self.client.post(url)
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('prestation(s) cochée(s)', reponse.data['detail'])
        self.assertIn('projet(s)', reponse.data['detail'])
        Projet.objects.all().delete()
        self.cocher(False)
        self.assertEqual(self.client.post(url).status_code, 204)
        self.assertFalse(Affaire.objects.filter(pk=self.affaire['id']).exists())

    def test_archivage(self):
        self.client.delete(f"/api/marches/affaires/{self.affaire['id']}/")
        self.assertEqual(self.client.get('/api/marches/affaires/').data['count'], 0)

    # --- Chaîne --------------------------------------------------------
    def test_cochage_des_prestations(self):
        self.cocher()
        url = f"/api/marches/prestations/?affaire={self.affaire['id']}&cochees=1"
        self.assertEqual(self.client.get(url).data['results'][0]['cochee'], True)
        self.cocher(False)
        self.assertEqual(self.client.get(url).data['count'], 0)

    def test_projet_seulement_sur_prestation_cochee(self):
        self.assertEqual(self.creer_projet().status_code, 400)
        self.cocher()
        self.assertEqual(self.creer_projet().status_code, 201)

    def test_numeros_de_projet_par_affaire(self):
        self.cocher()
        self.assertEqual(self.creer_projet('A').data['numero'], 1)
        self.assertEqual(self.creer_projet('B').data['numero'], 2)
        autre = self.client.post('/api/marches/affaires/', {
            'nom': 'Autre', 'responsables': [self.moi.id], 'membres': [self.moi.id]}).data
        self.client.post(f"/api/marches/affaires/{autre['id']}/prestations/", {'prestation': self.prestation['id']})
        projet = self.client.post('/api/marches/projets/', {
            'affaire': autre['id'], 'prestation': self.prestation['id'], 'nom': 'X',
            'rendement': self.prestation['rendements'][0]['id'], 'date_livraison': '2026-12-31'}).data
        self.assertEqual(projet['numero'], 1)   # repart à 1 dans l'autre affaire

    def test_decocher_une_prestation_avec_projets_refuse(self):
        self.cocher()
        self.creer_projet()
        self.assertEqual(self.cocher(False).status_code, 400)

    def test_descriptions_propres_a_chaque_projet(self):
        self.cocher()
        p1, p2 = self.creer_projet('A').data, self.creer_projet('B').data
        self.client.post('/api/marches/descriptions/', {'projet': p1['id'], 'nom': 'Vérification', 'quantite': '100'})
        self.client.post('/api/marches/descriptions/', {'projet': p2['id'], 'nom': 'Vérification', 'quantite': '5'})
        liste = self.client.get(f"/api/marches/descriptions/?projet={p2['id']}").data['results']
        self.assertEqual([(d['numero'], d['quantite']) for d in liste], [(1, '5.00')])   # seulement celle de B

    def test_quantite_du_projet_est_la_somme_des_descriptions(self):
        self.cocher()
        projet = self.creer_projet().data
        url = '/api/marches/descriptions/'
        d1 = self.client.post(url, {'projet': projet['id'], 'nom': 'Saisie', 'quantite': '1200'}).data
        self.client.post(url, {'projet': projet['id'], 'nom': 'Contrôle', 'quantite': '300,5'.replace(',', '.')})
        lire = lambda: self.client.get(f"/api/marches/projets/{projet['id']}/").data['quantite']
        self.assertEqual(lire(), '1500.50')
        self.client.patch(f"{url}{d1['id']}/", {'quantite': '200'})
        self.assertEqual(lire(), '500.50')
        self.client.delete(f"{url}{d1['id']}/")
        self.assertEqual(lire(), '300.50')

    def test_quantite_du_projet_non_saisissable(self):
        self.cocher()
        projet = self.creer_projet().data
        self.client.patch(f"/api/marches/projets/{projet['id']}/", {'quantite': '999'})
        self.assertIsNone(self.client.get(f"/api/marches/projets/{projet['id']}/").data['quantite'])

    def test_nom_de_description_unique_par_projet(self):
        self.cocher()
        projet = self.creer_projet().data
        self.client.post('/api/marches/descriptions/', {'projet': projet['id'], 'nom': 'X'})
        self.assertEqual(self.client.post('/api/marches/descriptions/', {'projet': projet['id'], 'nom': 'X'}).status_code, 400)

    # --- Outils communs ----------------------------------------------
    def test_reordonner(self):
        t1 = self.client.post('/api/marches/taches/', {'nom': 'Saisir'}).data
        t2 = self.client.post('/api/marches/taches/', {'nom': 'Contrôler'}).data
        self.client.post('/api/marches/taches/reordonner/', {'ids': [t2['id'], t1['id']]})
        noms = [t['nom'] for t in self.client.get('/api/marches/taches/').data['results']]
        self.assertEqual(noms, ['Contrôler', 'Saisir'])

    def test_export_excel(self):
        colonnes = json.dumps([{'cle': 'nom', 'libelle': 'Nom'}, {'cle': 'membres_details', 'libelle': 'Membres'}])
        reponse = self.client.get('/api/marches/affaires/exporter/', {'colonnes': colonnes, 'nom': 'Affaires'})
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('spreadsheetml', reponse['Content-Type'])
        from io import BytesIO

        from openpyxl import load_workbook
        feuille = load_workbook(BytesIO(reponse.content)).active
        self.assertEqual([c.value for c in feuille[2]][0], 'Recensement')


class MesMarchesEtArchivesTests(AuthentifieMixin, TestCase):
    """Mes marchés (responsable / membre), archives, statuts."""

    def setUp(self):
        super().setUp()
        self.client.get('/api/auth/moi/')
        self.moi = Employe.objects.get(code_barre='PR00001')
        # Ces tests préparent le Marché : superadmin (les droits par rôle sont testés dans autorisations)
        User.objects.filter(username='PR00001').update(is_staff=True, is_superuser=True)
        self.autre = Employe.objects.create(code_barre='PR2', nom='Rabe', prenom='Tiana')
        self.tiers = Employe.objects.create(code_barre='PR3', nom='Rakoto', prenom='Mamy')
        base = '/api/marches/affaires/'
        self.je_dirige = self.client.post(base, {'nom': 'Je dirige', 'responsables': [self.moi.id], 'membres': [self.autre.id]}).data
        self.je_participe = self.client.post(base, {'nom': 'Je participe', 'responsables': [self.autre.id], 'membres': [self.moi.id]}).data
        self.client.post(base, {'nom': 'Sans moi', 'responsables': [self.autre.id], 'membres': [self.tiers.id]})

    def test_mes_marches(self):
        roles = {a['nom']: a['mon_role'] for a in self.client.get('/api/marches/affaires/?mes=1').data['results']}
        self.assertEqual(roles, {'Je dirige': 'RESPONSABLE', 'Je participe': 'MEMBRE'})

    def test_un_responsable_modifie_les_membres(self):
        url = f"/api/marches/affaires/{self.je_dirige['id']}/membres/"
        reponse = self.client.post(url, {'membres': [self.autre.id, self.tiers.id]})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(len(reponse.data['membres_details']), 2)
        self.assertEqual(self.client.post(url, {'membres': []}).status_code, 400)   # au moins un membre

    def test_un_simple_membre_ne_modifie_pas_les_membres(self):
        User.objects.filter(username='PR00001').update(is_staff=False, is_superuser=False)   # droits de base
        url = f"/api/marches/affaires/{self.je_participe['id']}/membres/"
        self.assertEqual(self.client.post(url, {'membres': [self.tiers.id]}).status_code, 403)

    def test_archives_et_desarchivage(self):
        self.client.delete(f"/api/marches/affaires/{self.je_dirige['id']}/")
        archives = self.client.get('/api/marches/affaires/?archives=1').data['results']
        self.assertEqual([a['nom'] for a in archives], ['Je dirige'])
        self.assertNotIn('Je dirige', [a['nom'] for a in self.client.get('/api/marches/affaires/?mes=1').data['results']])
        self.client.post(f"/api/marches/affaires/{self.je_dirige['id']}/desarchiver/")
        self.assertEqual(self.client.get('/api/marches/affaires/?archives=1').data['count'], 0)

    def test_statuts(self):
        self.assertEqual(self.client.post('/api/marches/statuts/', {'nom': 'En cours'}).status_code, 201)
        self.assertEqual(self.client.post('/api/marches/statuts/', {'nom': 'En cours'}).status_code, 400)

    def test_couleur_des_statuts(self):
        self.assertEqual(self.client.post('/api/marches/statuts/', {'nom': 'Terminé', 'couleur': '#1e8a5a'}).data['couleur'], '#1E8A5A')
        self.assertEqual(self.client.post('/api/marches/statuts/', {'nom': 'Bloqué', 'couleur': 'rouge'}).status_code, 400)


class ImportExcelTests(AuthentifieMixin, TestCase):
    """Import des Affaires et des Prestations depuis un fichier .xlsx."""

    def setUp(self):
        super().setUp()
        self.client.get('/api/auth/moi/')
        self.moi = Employe.objects.get(code_barre='PR00001')
        # Ces tests préparent le Marché : superadmin (les droits par rôle sont testés dans autorisations)
        User.objects.filter(username='PR00001').update(is_staff=True, is_superuser=True)
        self.autre = Employe.objects.create(code_barre='PR2', nom='Rabe', prenom='Tiana')

    def fichier(self, lignes, nom='import.xlsx'):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from openpyxl import Workbook
        classeur = Workbook()
        for ligne in lignes:
            classeur.active.append(ligne)
        flux = BytesIO()
        classeur.save(flux)
        return SimpleUploadedFile(nom, flux.getvalue())

    def importer(self, ressource, lignes, simulation=False):
        donnees = {'fichier': self.fichier(lignes)}
        if simulation:
            donnees['simulation'] = '1'
        return self.client.post(f'/api/marches/{ressource}/importer/', donnees, format='multipart')

    def test_modeles_telechargeables(self):
        from io import BytesIO

        from openpyxl import load_workbook
        for ressource, onglets in (('prestations', ['Prestations', 'Aide']), ('affaires', ['Affaires', 'Aide', 'Personnes', 'Prestations'])):
            reponse = self.client.get(f'/api/marches/{ressource}/modele/')
            self.assertEqual(reponse.status_code, 200)
            self.assertEqual(load_workbook(BytesIO(reponse.content)).sheetnames, onglets)

    def test_import_des_prestations(self):
        lignes = [['Nom prestation *', 'Unité *', 'Rendement objectif 1 *', 'Rendement objectif 2'],
                  ['Saisie', 'fiches', 120, '80,5'],
                  ['Contrôle', 'pages', None, None],          # erreur : aucun rendement
                  ['Saisie', 'fiches', 150, None]]            # même nom : mise à jour
        rapport = self.importer('prestations', lignes).data
        self.assertEqual((rapport['crees'], rapport['modifies'], rapport['erreurs']), (1, 1, 1))
        self.assertEqual(rapport['lignes'][1]['numero'], 3)
        self.assertIn('Rendement objectif', rapport['lignes'][1]['messages'][0])
        self.assertEqual([str(r.valeur) for r in Prestation.objects.get(nom='Saisie').rendements.all()], ['150.00'])

    def test_simulation_n_enregistre_rien(self):
        rapport = self.importer('prestations', [['Nom prestation', 'Unité', 'Rendement objectif 1'], ['X', 'u', 5]], simulation=True).data
        self.assertEqual((rapport['simulation'], rapport['crees']), (True, 1))
        self.assertFalse(Prestation.objects.exists())

    def test_import_des_affaires(self):
        Prestation.objects.create(nom='Saisie', unite='fiches')
        lignes = [['Num affaire', 'Nom affaire *', 'Responsables *', 'Membres *', 'Prestations'],
                  ['AF-01', 'Recensement', 'PR00001', 'pr2; PR00001', 'Saisie'],
                  [None, 'Sans numéro', 'PR00001', 'TOUS', None],
                  ['AF-02', 'Mauvaise', 'PR999', 'PR2', 'Inconnue']]
        rapport = self.importer('affaires', lignes).data
        self.assertEqual((rapport['crees'], rapport['erreurs']), (2, 1))
        erreurs = ' '.join(rapport['lignes'][2]['messages'])
        self.assertIn('PR999', erreurs)
        affaire = Affaire.objects.get(num_affaire='AF-01')
        self.assertEqual(affaire.membres.count(), 2)
        self.assertEqual(list(affaire.prestations.values_list('nom', flat=True)), ['Saisie'])
        self.assertEqual(Affaire.objects.get(nom='Sans numéro').membres.count(), Employe.objects.count())
        # Réimport : même n° -> mise à jour
        rapport = self.importer('affaires', [lignes[0], ['AF-01', 'Recensement 2026', 'PR2', 'PR2', None]]).data
        self.assertEqual(rapport['modifies'], 1)
        self.assertEqual(Affaire.objects.get(num_affaire='AF-01').nom, 'Recensement 2026')
        # Deux affaires avec ce n° : la ligne est refusée (on ne sait pas laquelle modifier)
        Affaire.objects.create(nom='Doublon', num_affaire='AF-01')
        rapport = self.importer('affaires', [lignes[0], ['AF-01', 'X', 'PR2', 'PR2', None]]).data
        self.assertEqual(rapport['erreurs'], 1)
        self.assertIn('Plusieurs affaires', rapport['lignes'][0]['messages'][0])

    def test_fichier_invalide(self):
        reponse = self.client.post('/api/marches/prestations/importer/', {'fichier': self.fichier([['A', 'B']], 'x.csv')}, format='multipart')
        self.assertEqual(reponse.status_code, 400)
        reponse = self.client.post('/api/marches/prestations/importer/', {'fichier': self.fichier([['Autre colonne'], ['x']])}, format='multipart')
        self.assertIn('Colonne(s) introuvable(s)', reponse.data['detail'])


class DureeEstimativeTests(AuthentifieMixin, TestCase):
    """Marchés > Durée estimatif : temps estimatif, restant, filtres, ressources (export)."""

    def setUp(self):
        super().setUp()
        self.client.get('/api/auth/moi/')
        self.moi = Employe.objects.get(code_barre='PR00001')

    def test_duree_estimative(self):
        from datetime import date

        from gsheets.models import Feuille, LigneFeuille, PerimetreFeuille
        from gsheets.services import synchroniser
        from marches.models import Affaire, AffairePrestation, Description, Prestation, Projet, RendementObjectif, Statut
        self.assertEqual(self.client.get('/api/marches/duree-estimative/').status_code, 403)      # sans rôle (module « Durée estimatif »)
        User.objects.filter(username='PR00001').update(is_staff=True, is_superuser=True)
        prestation = Prestation.objects.create(nom='Saisie', unite='fiches')
        objectif = RendementObjectif.objects.create(prestation=prestation, valeur=2000)
        affaire = Affaire.objects.create(nom='Recensement')
        AffairePrestation.objects.create(affaire=affaire, prestation=prestation)
        projet = Projet.objects.create(affaire=affaire, prestation=prestation, nom='Commune 1', rendement=objectif, date_livraison=date(2026, 12, 31))
        menages = Description.objects.create(projet=projet, nom='Ménages', quantite=6000)
        Description.objects.create(projet=projet, nom='Bâtiments', quantite=2000)
        feuille = Feuille.objects.create(nom='Suivi', utiliser_criteres=False)
        PerimetreFeuille.objects.create(feuille=feuille, affaire=affaire, prestation=prestation)
        synchroniser(feuille)
        livre = Statut.objects.create(nom='Livré')
        LigneFeuille.objects.filter(description=menages).update(avancement=50, statut=livre)
        donnees = self.client.get('/api/marches/duree-estimative/').data
        p = donnees['projets'][0]
        self.assertEqual((p['quantite'], p['temps_heures']), (8000.0, 32.0))                   # 8 000 / 2 000 × 8 h
        self.assertEqual((p['quantite_restante'], p['temps_restant_heures']), (5000.0, 20.0))   # 3 000 + 2 000
        seulement = self.client.get('/api/marches/duree-estimative/', {'statuts': livre.id}).data['projets'][0]
        self.assertEqual(seulement['quantite'], 6000.0)                                          # descriptions « Livré »
        self.assertEqual(self.client.get('/api/marches/duree-estimative/', {'rendements': 999}).data['projets'], [])
        reponse = self.client.get('/api/marches/duree-estimative/exporter/', {'ressources': f'{{"{projet.id}": 2}}'})
        self.assertEqual(reponse.status_code, 200)


class ConfigurationsResponsablesTests(AuthentifieMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.get('/api/auth/moi/')
        self.moi = Employe.objects.get(code_barre='PR00001')
        self.jean = Employe.objects.create(code_barre='PR10', nom='Jean', prenom='Jean')

    def test_configurations(self):
        donnees = {'nom': 'Direction', 'personnes': [self.moi.id, self.jean.id], 'par_defaut': True}
        self.assertEqual(self.client.post('/api/marches/configurations-responsables/', donnees, format='json').status_code, 403)
        User.objects.filter(username='PR00001').update(is_staff=True, is_superuser=True)
        a = self.client.post('/api/marches/configurations-responsables/', donnees, format='json').data
        b = self.client.post('/api/marches/configurations-responsables/', {'nom': 'Saisie', 'personnes': [self.jean.id],
                                                                          'par_defaut': True}, format='json').data
        liste = {c['nom']: c for c in self.client.get('/api/marches/configurations-responsables/').data}
        self.assertEqual((liste['Direction']['par_defaut'], liste['Saisie']['par_defaut']), (False, True))   # une seule par défaut
        self.assertEqual(len(liste['Direction']['personnes_details']), 2)
        User.objects.filter(username='PR00001').update(is_staff=False, is_superuser=False)
        self.assertEqual(len(self.client.get('/api/marches/configurations-responsables/').data), 2)       # lecture pour tous
        self.assertEqual(self.client.delete(f"/api/marches/configurations-responsables/{a['id']}/").status_code, 403)
        self.assertIsNotNone(b)
