# backend/pointages/tests.py
"""Lancer : python manage.py test pointages"""
from datetime import date, time, timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from authentification.tests import AuthentifieMixin
from gsheets.tests import DonneesFeuilleMixin
from gsheets.models import LigneFeuille
from marches.models import Tache

from .calculs import calculer, repartir_journee

LUNDI = date(2026, 11, 2)
SAMEDI = date(2026, 11, 7)


def journee(jour, *creneaux):
    pointages = [SimpleNamespace(heure_debut=time(*d), heure_fin=time(*f)) for d, f in creneaux]
    resultat = repartir_journee(jour, pointages)
    return [resultat[id(p)] for p in pointages]


class CalculsTests(SimpleTestCase):
    """H_Durée et HS, en minutes (case « Pause (−1 h) » cochée par la personne)."""

    def calc(self, jour, debut, fin, pause=False):
        return calculer(jour, time(*debut), time(*fin), pause)

    def test_exemples_avec_la_pause(self):
        self.assertEqual(self.calc(LUNDI, (8, 0), (16, 30), pause=True), (450, 0))     # 7,5 h
        self.assertEqual(self.calc(LUNDI, (9, 0), (16, 30), pause=True), (390, 0))     # 6,5 h
        self.assertEqual(self.calc(LUNDI, (7, 30), (16, 30), pause=True), (480, 0))    # 8 h

    def test_sans_pause_rien_n_est_retire(self):
        self.assertEqual(self.calc(LUNDI, (7, 30), (16, 30)), (540, 0))
        self.assertEqual(self.calc(LUNDI, (7, 30), (12, 0)), (270, 0))

    def test_heures_sup(self):
        self.assertEqual(self.calc(LUNDI, (7, 0), (7, 30)), (0, 30))
        self.assertEqual(self.calc(LUNDI, (13, 0), (18, 0), pause=True), (150, 90))
        self.assertEqual(self.calc(LUNDI, (16, 0), (18, 0), pause=True), (0, 60))       # 30 min + 30 min de HS retirées

    def test_creneaux_libres(self):
        from .calculs import creneaux_libres, suggestion
        m = lambda h, mi=0: h * 60 + mi
        self.assertEqual(creneaux_libres([(m(7, 30), m(12))]), [(m(12), m(16, 30))])
        self.assertEqual(creneaux_libres([(m(7, 30), m(12)), (m(13), m(16, 30))]), [(m(12), m(13))])
        self.assertEqual(creneaux_libres([(m(8), m(10)), (m(9), m(11))]), [(m(7, 30), m(8)), (m(11), m(16, 30))])
        self.assertEqual(suggestion([(m(7, 30), m(12))]), (m(12), m(16, 30)))
        self.assertEqual(suggestion([(m(7, 30), m(17))]), (m(17), None))      # journée complète : après le dernier

    def test_week_end(self):
        self.assertEqual(self.calc(SAMEDI, (8, 0), (12, 0)), (0, 240))
        self.assertEqual(self.calc(SAMEDI, (8, 0), (17, 0), pause=True), (0, 480))


class PointageTests(DonneesFeuilleMixin, AuthentifieMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.production = Tache.objects.create(nom='Saisie', type='PRODUCTION')
        self.controle = Tache.objects.create(nom='Contrôle', type='CONTROLE')
        self.reunion = Tache.objects.create(nom='Réunion', type='AUTRE')
        self.feuille = self.creer().data
        self.ligne = LigneFeuille.objects.get(feuille_id=self.feuille['id'], numero=1)
        self.jour = date.today() - timedelta(days=(date.today().weekday() + 7))   # lundi de la semaine dernière

    def pointer(self, debut, fin, tache=None, description=None, client=None, jour=None, descriptions=None, commentaire='',
                pause=False):
        ids = [d.id for d in descriptions] if descriptions else [(description or self.ligne.description).id]
        return (client or self.client).post('/api/pointages/', {
            'date': (jour or self.jour).isoformat(), 'heure_debut': debut, 'heure_fin': fin, 'commentaire': commentaire,
            'pause': pause,
            'descriptions': ids, 'tache': (tache or self.production).id}, format='json')

    def test_pointage_place_et_reporte_dans_la_feuille(self):
        reponse = self.pointer('07:30', '12:00')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual((reponse.data['minutes_normales'], reponse.data['minutes_hs']), (270, 0))
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.employe.code_barre, 'PR00001')     # placé automatiquement
        self.assertEqual(str(self.ligne.temps_prod), '4.50')
        self.pointer('13:00', '17:00')                                  # 3h30 + 30 min de HS
        self.ligne.refresh_from_db()
        self.assertEqual(str(self.ligne.temps_prod), '8.50')

    def test_controle_reporte_dans_temps_de_controle(self):
        self.pointer('08:00', '09:00', tache=self.controle)
        self.ligne.refresh_from_db()
        self.assertEqual((self.ligne.controleur.code_barre, str(self.ligne.temps_controle), self.ligne.temps_prod), ('PR00001', '1.00', None))

    def test_tache_autre_ne_touche_pas_la_feuille(self):
        self.pointer('08:00', '09:00', tache=self.reunion)
        self.ligne.refresh_from_db()
        self.assertEqual((self.ligne.employe, self.ligne.temps_prod), (None, None))

    def test_refus_si_quelqu_un_d_autre_est_place(self):
        self.client.patch(f'/api/gsheets/lignes/{self.ligne.id}/', {'employe': self.membre.id})
        reponse = self.pointer('08:00', '09:00')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('PR2_Tiana', reponse.data['detail'])

    def test_colonne_verrouillee_dans_la_feuille(self):
        self.pointer('08:00', '09:00')
        reponse = self.client.patch(f'/api/gsheets/lignes/{self.ligne.id}/', {'employe': self.membre.id})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('verrouillée', reponse.data['detail'])
        lignes = self.client.get('/api/gsheets/lignes/', {'feuille': self.feuille['id']}).data['results']
        self.assertEqual(lignes[0]['colonnes_verrouillees'], ['employe'])

    def test_suppression_recalcule_et_deverrouille(self):
        p = self.pointer('08:00', '09:00').data
        self.client.delete(f"/api/pointages/{p['id']}/")
        self.ligne.refresh_from_db()
        self.assertIsNone(self.ligne.temps_prod)
        self.assertEqual(self.client.patch(f'/api/gsheets/lignes/{self.ligne.id}/', {'employe': self.membre.id}).status_code, 200)

    def test_pause_retire_une_heure(self):
        p = self.pointer('08:00', '16:30', pause=True).data
        self.assertEqual((p['minutes_normales'], p['pause']), (450, True))                # 7,5 h
        self.assertEqual(self.pointer('16:30', '18:00').data['minutes_normales'], 0)      # HS, pas de pause

    def test_une_seule_pause_par_jour(self):
        self.pointer('07:30', '12:00', pause=True)
        reponse = self.pointer('13:00', '16:30', pause=True)
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('07:30–12:00', str(reponse.data))

    def test_pause_non_cochee_est_une_erreur(self):
        self.pointer('07:30', '12:00')
        self.pointer('13:00', '16:30')
        erreurs = self.client.get('/api/pointages/resume/', {'debut': self.jour, 'fin': self.jour}).data['erreurs']
        self.assertEqual([e['type'] for e in erreurs], ['PAUSE'])
        p = self.client.get('/api/pointages/', {'debut': self.jour, 'fin': self.jour}).data['results'][0]
        self.client.patch(f"/api/pointages/{p['id']}/", {'pause': True}, format='json')
        erreurs = self.client.get('/api/pointages/resume/', {'debut': self.jour, 'fin': self.jour}).data['erreurs']
        self.assertEqual([e['type'] for e in erreurs], ['INCOMPLET'])                      # 7 h après la pause

    def test_pause_le_week_end_facultative(self):
        samedi = self.jour + timedelta(days=5)
        self.pointer('08:00', '12:00', jour=samedi)
        self.assertEqual(self.client.get('/api/pointages/resume/', {'debut': samedi, 'fin': samedi}).data['erreurs'], [])

    def test_chevauchement_refuse(self):
        self.pointer('08:00', '10:00')
        self.assertEqual(self.pointer('09:30', '11:00').status_code, 400)
        self.assertEqual(self.pointer('10:00', '11:00').status_code, 201)   # bout à bout : accepté

    def test_controles_de_saisie(self):
        self.assertEqual(self.pointer('10:00', '09:00').status_code, 400)
        self.assertEqual(self.pointer('08:00', '09:00', jour=date.today() + timedelta(days=1)).status_code, 201)   # date à venir acceptée

    def test_ligne_d_une_affaire_dont_je_ne_suis_pas_membre(self):
        self.affaire.responsables.set([self.membre])
        self.affaire.membres.set([self.membre])
        self.assertEqual(self.pointer('08:00', '09:00').status_code, 400)

    def test_pointage_rattache_a_la_ligne_de_la_description(self):
        p = self.pointer('08:00', '09:00').data
        self.assertEqual(p['parts'][0]['numero_ligne'], self.ligne.numero)
        self.assertEqual((p['marche']['description'], p['marche']['feuille']), ('Ménages', 'Suivi novembre'))

    def test_description_hors_feuille_enregistree_sans_report(self):
        from marches.models import Description, Projet
        projet = Projet.objects.create(affaire=self.affaire, prestation=self.prestation, nom='Commune B',
                                       rendement=self.projet.rendement, date_livraison='2026-12-31')
        # La feuille existe déjà : la nouvelle description y entre. On en crée une sur une autre prestation.
        from marches.models import AffairePrestation, Prestation, RendementObjectif
        autre = Prestation.objects.create(nom='Contrôle qualité', unite='pages')
        AffairePrestation.objects.create(affaire=self.affaire, prestation=autre)
        projet_hors = Projet.objects.create(affaire=self.affaire, prestation=autre, nom='Commune C',
                                            rendement=RendementObjectif.objects.create(prestation=autre, valeur=10),
                                            date_livraison='2026-12-31')
        hors = Description.objects.create(projet=projet_hors, nom='Hors feuille')
        reponse = self.pointer('08:00', '09:00', description=hors)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertIsNone(reponse.data['parts'][0]['feuille'])
        self.assertIsNone(reponse.data['marche']['feuille'])
        self.assertIsNotNone(projet)

    def test_mes_affaires_par_priorite(self):
        from marches.models import Affaire, Statut
        hors_feuille = Affaire.objects.create(nom='A hors feuille')
        hors_feuille.responsables.set([self.moi])
        hors_feuille.membres.set([self.moi])
        noms = [a['nom'] for a in self.client.get('/api/pointages/affaires/').data['results']]
        self.assertEqual(noms, ['Recensement', 'A hors feuille'])      # celle de la feuille d'abord
        # Placé sur une ligne au statut prioritaire : reste en tête, avec les indicateurs
        prioritaire = Statut.objects.create(nom='Prioritaire', prioritaire_pointage=True)
        self.client.patch(f'/api/gsheets/lignes/{self.ligne.id}/', {'employe': self.moi.id, 'statut': prioritaire.id})
        premiere = self.client.get('/api/pointages/affaires/').data['results'][0]
        self.assertEqual((premiere['nom'], premiere['place'], premiere['prioritaire']), ('Recensement', True, True))

    def test_arborescence_d_une_affaire(self):
        self.client.patch(f'/api/gsheets/lignes/{self.ligne.id}/', {'employe': self.moi.id})
        arbre = self.client.get('/api/pointages/arborescence/', {'affaire': self.affaire.id}).data
        prestation = arbre['prestations'][0]
        description = prestation['projets'][0]['descriptions'][0]
        self.assertEqual((prestation['nom'], description['nom']), ('Saisie', 'Ménages'))
        self.assertEqual(description['ligne']['mes_roles'], ['PRODUCTION'])
        self.assertEqual(description['ligne']['feuille'], 'Suivi novembre')

    def test_une_affaire_prestation_dans_une_seule_feuille(self):
        reponse = self.creer()
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('déjà dans la feuille', reponse.data['detail'])

    def test_description_pointee_non_supprimable(self):
        from marches.models import Description
        self.pointer('08:00', '09:00', tache=self.reunion)      # tâche « Autre » : la ligne reste vide
        reponse = self.client.delete(f'/api/marches/descriptions/{self.ligne.description_id}/')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('utilisé par : 1 pointage', reponse.data['detail'])
        self.assertTrue(Description.objects.filter(pk=self.ligne.description_id).exists())

    # --- Plusieurs descriptions -------------------------------------------
    def test_temps_partage_au_prorata_des_quantites(self):
        # Ménages : 100, Établissements : 40 -> 4 h partagées en 2h51 et 1h09 (171 + 69 minutes)
        self.production.plusieurs_descriptions = True
        self.production.save()
        deux = LigneFeuille.objects.get(feuille_id=self.feuille['id'], numero=2)
        reponse = self.pointer('08:00', '12:00', descriptions=[self.ligne.description, deux.description])
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual([p['minutes'] for p in reponse.data['parts']], [171, 69])
        self.assertEqual(reponse.data['marche']['description'], 'Ménages, Établissements')
        self.ligne.refresh_from_db()
        deux.refresh_from_db()
        self.assertEqual((str(self.ligne.temps_prod), str(deux.temps_prod)), ('2.85', '1.15'))
        self.assertEqual((self.ligne.employe_id, deux.employe_id), (self.moi.id, self.moi.id))

    def test_parts_egales_si_une_quantite_manque(self):
        self.production.plusieurs_descriptions = True
        self.production.save()
        deux = LigneFeuille.objects.get(feuille_id=self.feuille['id'], numero=2)
        deux.description.quantite = None
        deux.description.save()
        parts = self.pointer('08:00', '10:00', descriptions=[self.ligne.description, deux.description]).data['parts']
        self.assertEqual([p['minutes'] for p in parts], [60, 60])

    def test_plusieurs_descriptions_seulement_si_la_tache_le_permet(self):
        deux = LigneFeuille.objects.get(feuille_id=self.feuille['id'], numero=2)
        reponse = self.pointer('08:00', '10:00', descriptions=[self.ligne.description, deux.description])
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('une seule description', str(reponse.data))

    def test_plusieurs_descriptions_du_meme_projet(self):
        from marches.models import Description, Projet
        self.production.plusieurs_descriptions = True
        self.production.save()
        autre_projet = Projet.objects.create(affaire=self.affaire, prestation=self.prestation, nom='Commune B',
                                             rendement=self.projet.rendement, date_livraison='2026-12-31')
        autre = Description.objects.create(projet=autre_projet, nom='Autre', quantite=10)
        reponse = self.pointer('08:00', '10:00', descriptions=[self.ligne.description, autre])
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('même projet', str(reponse.data))

    # --- Commentaires ------------------------------------------------------
    def test_commentaire_ajoute_dans_la_colonne_du_type(self):
        self.pointer('08:00', '09:00', commentaire='Saisie commencée')
        self.pointer('09:00', '10:00', tache=self.controle, commentaire='Contrôle OK')
        self.pointer('10:00', '11:00', commentaire='Saisie terminée')
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.commentaires.count('PR00001_Jean'), 2)
        self.assertIn(' | ', self.ligne.commentaires)
        self.assertIn('Saisie terminée', self.ligne.commentaires)
        self.assertIn('Contrôle OK', self.ligne.commentaires_controle)
        self.assertEqual(self.ligne.commentaires_reprise, '')

    def test_commentaires_toujours_modifiables_dans_la_feuille(self):
        self.pointer('08:00', '09:00', tache=self.controle, commentaire='Contrôle OK')
        reponse = self.client.patch(f'/api/gsheets/lignes/{self.ligne.id}/', {'commentaires_controle': 'Corrigé à la main'})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data['commentaires_controle'], 'Corrigé à la main')

    # --- Retrait à la suppression -----------------------------------------
    def test_suppression_retire_la_personne_et_le_commentaire(self):
        self.client.patch(f'/api/gsheets/lignes/{self.ligne.id}/', {'commentaires': 'Note du chef'})
        p = self.pointer('08:00', '09:00', commentaire='Lot 1').data
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.employe_id, self.moi.id)
        self.assertIn('Lot 1', self.ligne.commentaires)
        self.client.delete(f"/api/pointages/{p['id']}/")
        self.ligne.refresh_from_db()
        self.assertIsNone(self.ligne.employe_id)
        self.assertEqual(self.ligne.commentaires, 'Note du chef')       # le reste est conservé

    def test_la_personne_reste_si_elle_a_un_autre_pointage(self):
        p1 = self.pointer('08:00', '09:00', commentaire='Lot 1').data
        self.pointer('09:00', '10:00', commentaire='Lot 2')
        self.client.delete(f"/api/pointages/{p1['id']}/")
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.employe_id, self.moi.id)
        self.assertNotIn('Lot 1', self.ligne.commentaires)
        self.assertIn('Lot 2', self.ligne.commentaires)

    def test_retrait_selon_le_type_de_la_tache(self):
        self.pointer('08:00', '09:00')                                   # production : reste
        p = self.pointer('09:00', '10:00', tache=self.controle, commentaire='Vu').data
        self.client.delete(f"/api/pointages/{p['id']}/")
        self.ligne.refresh_from_db()
        self.assertEqual((self.ligne.employe_id, self.ligne.controleur_id, self.ligne.commentaires_controle),
                         (self.moi.id, None, ''))

    def test_modifier_le_commentaire_remplace_l_ancien(self):
        p = self.pointer('08:00', '09:00', commentaire='Premier').data
        self.client.patch(f"/api/pointages/{p['id']}/", {'commentaire': 'Corrigé'}, format='json')
        self.ligne.refresh_from_db()
        self.assertNotIn('Premier', self.ligne.commentaires)
        self.assertIn('Corrigé', self.ligne.commentaires)

    def test_changer_de_description_libere_l_ancienne_ligne(self):
        deux = LigneFeuille.objects.get(feuille_id=self.feuille['id'], numero=2)
        p = self.pointer('08:00', '09:00', commentaire='Lot').data
        self.client.patch(f"/api/pointages/{p['id']}/", {'descriptions': [deux.description_id]}, format='json')
        self.ligne.refresh_from_db()
        deux.refresh_from_db()
        self.assertEqual((self.ligne.employe_id, self.ligne.temps_prod, self.ligne.commentaires), (None, None, ''))
        self.assertEqual(deux.employe_id, self.moi.id)
        self.assertIn('Lot', deux.commentaires)

    # --- Import Excel ------------------------------------------------------
    def test_import_de_pointages(self):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from openpyxl import Workbook, load_workbook
        modele = load_workbook(BytesIO(self.client.get('/api/pointages/modele/').content))
        self.assertEqual(modele.sheetnames, ['Pointages', 'Aide', 'Descriptions', 'Tâches'])
        classeur = Workbook()
        for ligne in [['Date', 'H_Début', 'H_Fin', 'Tâche', 'ID description', 'Commentaire'],
                      [self.jour.strftime('%d/%m/%Y'), '07:30', '12:00', 'saisie', self.ligne.description_id, 'Importé'],
                      [self.jour.strftime('%d/%m/%Y'), '11:00', '13:00', 'Saisie', self.ligne.description_id, None],   # chevauche
                      [self.jour.strftime('%d/%m/%Y'), '13:00', '14:00', 'Inconnue', self.ligne.description_id, None]]:
            classeur.active.append(ligne)
        flux = BytesIO()
        classeur.save(flux)
        rapport = self.client.post('/api/pointages/importer/', {'fichier': SimpleUploadedFile('p.xlsx', flux.getvalue())},
                                   format='multipart').data
        self.assertEqual((rapport['crees'], rapport['erreurs']), (1, 2), rapport)
        self.ligne.refresh_from_db()
        self.assertEqual(str(self.ligne.temps_prod), '4.50')
        self.assertIn('Importé', self.ligne.commentaires)

    # --- Date de début --------------------------------------------------------
    def test_date_de_debut_premiere_date_pointee(self):
        self.pointer('08:00', '09:00', jour=self.jour + timedelta(days=2))
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.date_debut, self.jour + timedelta(days=2))
        p = self.pointer('08:00', '09:00', tache=self.reunion, jour=self.jour).data   # toute tâche compte
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.date_debut, self.jour)
        self.client.delete(f"/api/pointages/{p['id']}/")
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.date_debut, self.jour + timedelta(days=2))

    def test_date_de_debut_d_un_pointage_fait_avant_la_feuille(self):
        from marches.models import AffairePrestation, Description, Prestation, Projet, RendementObjectif
        autre = Prestation.objects.create(nom='Contrôle qualité', unite='pages')
        AffairePrestation.objects.create(affaire=self.affaire, prestation=autre)
        projet = Projet.objects.create(affaire=self.affaire, prestation=autre, nom='Commune C',
                                       rendement=RendementObjectif.objects.create(prestation=autre, valeur=10),
                                       date_livraison='2026-12-31')
        description = Description.objects.create(projet=projet, nom='Avant la feuille', quantite=5)
        self.pointer('08:00', '09:00', description=description)
        feuille = self.client.post('/api/gsheets/feuilles/', {
            'nom': 'Nouvelle', 'perimetres_saisis': [{'affaire': self.affaire.id, 'prestation': autre.id}]}, format='json').data
        self.assertEqual(LigneFeuille.objects.get(feuille_id=feuille['id']).date_debut, self.jour)

    # --- Temps du Marché ---------------------------------------------------------
    def temps_marche(self, ressource, tache=None, **filtres):
        parametres = {**filtres, **({'tache': tache.id} if tache else {})}
        return self.client.get(f'/api/marches/{ressource}/', parametres).data['results'][0]

    def test_tache_ajoutee_au_temps_du_projet(self):
        self.reunion.temps_projet = True
        self.reunion.save()
        self.pointer('08:00', '10:00')                                   # Saisie : 2 h dans la feuille
        self.pointer('10:00', '11:00', tache=self.reunion)               # Réunion : 1 h, hors feuille
        description = self.temps_marche('descriptions', projet=self.projet.id)
        projet = self.temps_marche('projets', affaire=self.affaire.id, prestation=self.prestation.id)
        affaire = self.temps_marche('affaires')
        self.assertEqual(description['temps'], '2.00')                  # la description ne compte que la feuille
        self.assertEqual((projet['temps'], affaire['temps']), ('3.00', '3.00'))

    def test_pas_de_double_comptage(self):
        self.production.temps_projet = True                              # déjà comptée dans la feuille
        self.production.save()
        self.pointer('08:00', '10:00')
        self.assertEqual(self.temps_marche('projets', affaire=self.affaire.id, prestation=self.prestation.id)['temps'], '2.00')

    def test_tache_non_cochee_non_ajoutee(self):
        self.pointer('10:00', '11:00', tache=self.reunion)
        self.assertIsNone(self.temps_marche('projets', affaire=self.affaire.id, prestation=self.prestation.id)['temps'])

    def test_temps_d_une_tache_choisie(self):
        self.pointer('08:00', '10:00')
        self.pointer('10:00', '10:30', tache=self.controle)
        self.assertEqual(self.temps_marche('projets', tache=self.controle, affaire=self.affaire.id, prestation=self.prestation.id)['temps_tache'], '0.50')
        self.assertEqual(self.temps_marche('affaires', tache=self.production)['temps_tache'], '2.00')
        prestation = self.temps_marche('prestations', tache=self.production, affaire=self.affaire.id)
        self.assertEqual(prestation['temps_tache'], '2.00')
        self.assertIsNone(self.temps_marche('affaires')['temps_tache'])   # aucune tâche choisie

    # --- Suivi et Vérification (superadmins) -----------------------------------
    def devenir_admin(self):
        from django.contrib.auth.models import User
        User.objects.filter(username='PR00001').update(is_staff=True, is_superuser=True)

    def test_suivi_selon_les_droits(self):
        """Suivi : aucun droit de base (même pour un responsable) ; un rôle donne son périmètre."""
        parametres = {'debut': self.jour, 'fin': self.jour}
        self.pointer('08:00', '09:00', client=self.client_de('PR2'))                 # Tiana, membre de mon affaire
        self.assertEqual(self.client.get('/api/pointages/tous/', parametres).status_code, 403)
        from autorisations.models import AttributionRole, DroitRole, Role
        role = Role.objects.create(nom='Suivi de mes affaires')
        DroitRole.objects.create(role=role, module='pointages_suivi', action='voir', perimetre='MEMBRES_AFFAIRES')
        AttributionRole.objects.create(role=role, critere='MATRICULE', employe=self.moi)
        lignes = self.client.get('/api/pointages/tous/', parametres).data['results']
        self.assertEqual([l['employe_details']['code_barre'] for l in lignes], ['PR2'])
        self.assertEqual(self.client_de('PR2').get('/api/pointages/verification/', parametres).status_code, 403)

    def test_suivi_voit_tout_le_monde(self):
        self.pointer('08:00', '09:00')
        self.pointer('09:00', '10:00', client=self.client_de('PR2'), tache=self.controle)
        self.devenir_admin()
        parametres = {'debut': self.jour, 'fin': self.jour}
        donnees = self.client.get('/api/pointages/tous/', parametres).data
        self.assertEqual({p['employe_details']['code_barre'] for p in donnees['results']}, {'PR00001', 'PR2'})
        self.assertEqual(self.client.get('/api/pointages/tous/', {**parametres, 'employe': self.membre.id}).data['count'], 1)
        self.assertEqual(self.client.get('/api/pointages/tous/resume/', parametres).data['nb_personnes'], 2)

    def test_suivi_modifie_et_supprime_au_nom_de_la_personne(self):
        p = self.pointer('08:00', '09:00', client=self.client_de('PR2')).data
        self.devenir_admin()
        reponse = self.client.patch(f"/api/pointages/tous/{p['id']}/", {'heure_fin': '10:30'}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual((reponse.data['minutes_normales'], reponse.data['employe_details']['code_barre']), (150, 'PR2'))
        self.ligne.refresh_from_db()
        self.assertEqual(str(self.ligne.temps_prod), '2.50')
        self.assertEqual(self.client.delete(f"/api/pointages/tous/{p['id']}/").status_code, 204)
        self.ligne.refresh_from_db()
        self.assertEqual((self.ligne.temps_prod, self.ligne.employe_id), (None, None))

    def test_suivi_exclut_les_personnes_sans_acces(self):
        from autorisations.models import RegleAcces
        self.pointer('08:00', '09:00', client=self.client_de('PR2'))
        RegleAcces.objects.create(critere='MATRICULE', employe=self.moi)       # seul PR00001 a accès
        self.devenir_admin()
        self.assertEqual(self.client.get('/api/pointages/tous/', {'debut': self.jour, 'fin': self.jour}).data['count'], 0)

    def test_verification(self):
        samedi = self.jour + timedelta(days=5)
        self.pointer('07:30', '12:00')                                          # lundi : 4,5 h -> manque 3,5 h
        self.pointer('17:00', '18:00')                                          # HS : ne comble pas
        self.pointer('08:00', '10:00', jour=samedi)                             # samedi : manque 0
        self.pointer('07:30', '16:30', client=self.client_de('PR2'), tache=self.controle, pause=True)   # Tiana : 8 h
        self.devenir_admin()
        lignes = self.client.get('/api/pointages/verification/', {'debut': self.jour, 'fin': samedi}).data['results']
        resume = {(l['date'], l['employe']['code_barre']): (l['heures'], l['manque']) for l in lignes}
        self.assertEqual(resume, {
            (self.jour.isoformat(), 'PR00001'): (4.5, 3.5),
            (self.jour.isoformat(), 'PR2'): (8.0, 0.0),
            (samedi.isoformat(), 'PR00001'): (0.0, 0.0),
        })
        manques = self.client.get('/api/pointages/verification/', {'debut': self.jour, 'fin': samedi, 'manques': 1}).data['results']
        self.assertEqual(len(manques), 1)
        export = self.client.get('/api/pointages/verification/exporter/', {
            'debut': self.jour, 'fin': samedi, 'colonnes': '[{"cle":"date","libelle":"Date"},{"cle":"manque","libelle":"Manque"}]'})
        self.assertEqual(export.status_code, 200)

    def test_test_affaires_d_une_autre_personne_pour_l_admin(self):
        self.devenir_admin()
        from marches.models import Affaire
        autre = Affaire.objects.create(nom='Seulement Tiana')
        autre.responsables.set([self.membre])
        autre.membres.set([self.membre])
        noms = {a['nom'] for a in self.client.get('/api/pointages/affaires/', {'employe': self.membre.id}).data['results']}
        self.assertIn('Seulement Tiana', noms)

    def test_creneaux_proposes(self):
        self.pointer('07:30', '12:00')
        donnees = self.client.get('/api/pointages/creneaux/', {'date': self.jour}).data
        self.assertEqual((donnees['libres'], donnees['suggestion']), ([['12:00', '16:30']], {'debut': '12:00', 'fin': '16:30'}))
        self.pointer('13:00', '16:30')
        donnees = self.client.get('/api/pointages/creneaux/', {'date': self.jour}).data
        self.assertEqual(donnees['suggestion'], {'debut': '12:00', 'fin': '13:00'})

    # --- Affichage Everwin ---------------------------------------------------------
    def test_everwin_une_semaine_par_affaire(self):
        mardi = self.jour + timedelta(days=1)
        self.pointer('07:30', '16:30', commentaire='Lot 1', pause=True)        # lundi : 8 h
        self.pointer('16:30', '17:30')                                            # lundi : + 1 h HS
        self.pointer('08:00', '12:00', jour=mardi, tache=self.controle)          # mardi : 4 h
        grille = self.client.get('/api/pointages/everwin/', {'semaine': mardi}).data
        self.assertEqual([j['nom'] for j in grille['jours']][:2], ['Lundi', 'Mardi'])
        # Même affaire, deux tâches : deux lignes
        self.assertEqual([(a['nom'], a['tache'], a['total_minutes']) for a in grille['affaires']],
                         [('Recensement', 'Saisie', 540), ('Recensement', 'Contrôle', 240)])
        affaire = grille['affaires'][0]
        lundi = affaire['jours'][self.jour.isoformat()]
        self.assertEqual(lundi['minutes'], 540)                                   # H_Durée + HS
        self.assertEqual(lundi['details'][0]['commentaire'], 'Lot 1')
        totaux = grille['totaux']
        self.assertFalse(totaux[self.jour.isoformat()]['incomplet'])             # 8 h de H_Durée
        self.assertTrue(totaux[mardi.isoformat()]['incomplet'])                  # 4 h
        self.assertFalse(totaux[(self.jour + timedelta(days=5)).isoformat()]['incomplet'])   # samedi
        self.assertEqual(grille['chef'], None)

    def test_everwin_d_une_autre_personne(self):
        """Affichage Everwin : chacun le sien par défaut ; un rôle donne celui des autres (périmètre)."""
        self.pointer('08:00', '10:00', client=self.client_de('PR2'))
        moi = self.client.get('/api/pointages/everwin/', {'semaine': self.jour}).data
        self.assertEqual((moi['employe']['code_barre'], moi['peut_choisir']), ('PR00001', False))
        reponse = self.client.get('/api/pointages/everwin/', {'semaine': self.jour, 'employe': self.membre.id})
        self.assertEqual(reponse.status_code, 403)                                  # pas de droit sur Tiana
        from autorisations.models import AttributionRole, DroitRole, Role
        role = Role.objects.create(nom='Everwin équipe')
        DroitRole.objects.create(role=role, module='affichage_everwin', action='voir', perimetre='MEMBRES_AFFAIRES')
        AttributionRole.objects.create(role=role, critere='MATRICULE', employe=self.moi)
        grille = self.client.get('/api/pointages/everwin/', {'semaine': self.jour, 'employe': self.membre.id}).data
        self.assertEqual((grille['employe']['code_barre'], grille['total_minutes'], grille['peut_choisir']), ('PR2', 120, True))
        self.assertEqual([p['code_barre'] for p in self.client.get('/api/pointages/everwin/personnes/', {'recherche': 'PR2'}).data], ['PR2'])
        # Exporter celui de Tiana : pas dans le rôle ; le sien : droit de base
        self.assertEqual(self.client.get('/api/pointages/everwin/exporter/', {'semaine': self.jour, 'employe': self.membre.id}).status_code, 403)
        self.assertEqual(self.client.get('/api/pointages/everwin/exporter/', {'semaine': self.jour}).status_code, 200)

    def test_rendement_sans_affaire_cochee_et_commentaires(self):
        """Aucune affaire cochée : toutes ; une prestation seule suffit ; filtres des commentaires."""
        from rendements.models import ParametresGraphiques
        self.pointer('08:00', '12:00')                                   # moi, Ménages (100) : 4 h
        LigneFeuille.objects.filter(pk=self.ligne.pk).update(commentaires='Fiches illisibles', commentaires_controle='')
        donnees = self.client.get('/api/rendements/globale/').data
        self.assertEqual(donnees['employes'][0]['identifiant'], 'PR00001_Jean')   # sans affaire cochée
        prestation = self.client.get('/api/rendements/globale/', {'prestations': self.ligne.description.projet.prestation_id}).data
        self.assertTrue(prestation['employes'])
        import json
        options = self.client.get('/api/rendements/analyse/options/').data
        self.assertEqual([c['nom'] for c in options['commentaires']], ['Sans commentaire', 'Fiches illisibles'])
        coche = self.client.get('/api/rendements/globale/', {'commentaires': json.dumps(['Fiches illisibles'])}).data
        self.assertTrue(any(e['rendement'] for e in coche['employes']))
        sans = self.client.get('/api/rendements/globale/', {'commentaires': json.dumps(['__sans__'])}).data
        self.assertFalse(any(e['rendement'] for e in sans['employes']))
        controle = self.client.get('/api/rendements/globale/', {'commentaires_controle': json.dumps(['__sans__'])}).data
        self.assertTrue(any(e['rendement'] for e in controle['employes']))       # contrôle vide : « Sans commentaire »
        ParametresGraphiques.actuels().courbe1_taches.set([self.production])
        self.assertTrue(self.client.get('/api/rendements/evolution/').data['dates'])          # Evolution aussi

    # --- Page Rendement ------------------------------------------------------------
    def test_rendements(self):
        deux = LigneFeuille.objects.get(feuille_id=self.feuille['id'], numero=2)        # Établissements : 40
        self.pointer('08:00', '12:00')                                                   # moi, Saisie, Ménages (100) : 4 h
        self.pointer('13:00', '14:00', tache=self.controle)                              # moi, Contrôle : 1 h
        self.pointer('08:00', '10:00', description=deux.description, client=self.client_de('PR2'))   # Tiana : 2 h
        self.affaire.membres.add(self.moi)
        # Aucune affaire cochée : rien
        self.assertEqual(self.client.get('/api/rendements/analyse/').data['barres'], [])
        a = {'affaires': self.affaire.id}
        donnees = self.client.get('/api/rendements/analyse/', a).data
        self.assertEqual((donnees['niveau'], donnees['unite']), ('prestations', 'fiches'))
        barre = donnees['barres'][0]
        self.assertEqual((barre['nom'], barre['quantite'], barre['heures'], round(barre['rendement'], 2), barre['objectif']),
                         ('Saisie', 140.0, 7.0, 160.0, 120.0))
        self.assertEqual(round(donnees['equipes']['rendement'], 2), 160.0)
        personnes = {p['identifiant']: (p['quantite'], p['heures'], round(p['rendement'], 2)) for p in donnees['personnes']}
        self.assertEqual(personnes, {'PR00001_Jean': (100.0, 5.0, 160.0), 'PR2_Tiana': (40.0, 2.0, 160.0)})
        # Niveaux en dessous : projets, puis descriptions
        b = {**a, 'prestations': self.prestation.id}
        self.assertEqual(self.client.get('/api/rendements/analyse/', b).data['niveau'], 'projets')
        c = {**b, 'projets': self.projet.id, 'taches': self.production.id}
        donnees = self.client.get('/api/rendements/analyse/', c).data
        self.assertEqual([(x['nom'], x['heures']) for x in donnees['barres']], [('Ménages', 4.0), ('Établissements', 2.0)])
        self.assertEqual(round(donnees['equipes']['rendement'], 2), 186.67)                # tâche Saisie : 140 / 6 h × 8

    def test_rendements_unites_differentes(self):
        from marches.models import AffairePrestation, Description, Prestation, Projet, RendementObjectif
        autre = Prestation.objects.create(nom='Contrôle qualité', unite='pages')
        AffairePrestation.objects.create(affaire=self.affaire, prestation=autre)
        projet = Projet.objects.create(affaire=self.affaire, prestation=autre, nom='Commune C',
                                       rendement=RendementObjectif.objects.create(prestation=autre, valeur=10), date_livraison='2026-12-31')
        Description.objects.create(projet=projet, nom='Pages', quantite=50)
        self.pointer('08:00', '12:00')
        donnees = self.client.get('/api/rendements/analyse/', {'affaires': self.affaire.id}).data
        self.assertEqual((donnees['unite'], donnees['unites']), (None, ['fiches', 'pages']))
        self.assertEqual(sorted(b['unite'] for b in donnees['barres']), ['fiches', 'pages'])
        self.assertIsNone(donnees['equipes']['rendement'])                                # pas de total mélangé

    def test_rendements_filtre_par_statut(self):
        from marches.models import Statut
        termine = Statut.objects.create(nom='Terminé', active_note_rendement=True)
        self.pointer('08:00', '12:00')
        a = {'affaires': self.affaire.id, 'statut': termine.id}
        self.assertEqual(self.client.get('/api/rendements/analyse/', a).data['barres'], [])
        LigneFeuille.objects.filter(feuille_id=self.feuille['id']).update(statut=termine)
        self.assertEqual(len(self.client.get('/api/rendements/analyse/', a).data['barres']), 1)

    def test_rendement_globale(self):
        deux = LigneFeuille.objects.get(feuille_id=self.feuille['id'], numero=2)        # Établissements : 40
        self.pointer('08:00', '12:00')                                                   # moi, Saisie, Ménages (100) : 4 h
        self.pointer('13:00', '14:00', tache=self.controle)                              # moi, Contrôle sur Ménages : 1 h
        self.pointer('08:00', '10:00', description=deux.description, client=self.client_de('PR2'))   # Tiana : 2 h
        self.affaire.membres.add(self.moi)
        a = {'affaires': self.affaire.id}
        donnees = self.client.get('/api/rendements/globale/', a).data
        employes = {e['identifiant']: e for e in donnees['employes']}
        moi, tiana = employes['PR00001_Jean'], employes['PR2_Tiana']
        self.assertEqual((moi['quantite'], moi['heures'], round(moi['rendement'], 2)), (100.0, 5.0, 160.0))   # 100 / 5 h × 8
        self.assertEqual((round(tiana['rendement'], 2), tiana['objectif'], round(tiana['rentabilite'], 2)), (160.0, 120.0, 1.33))
        self.assertEqual({t['nom']: t['heures'] for t in donnees['temps_par_tache']}, {'Saisie': 6.0, 'Contrôle': 1.0})
        # Filtre par employé et par tâche
        seul = self.client.get('/api/rendements/globale/', {**a, 'employes': self.membre.id, 'taches': self.production.id}).data
        self.assertEqual([e['identifiant'] for e in seul['employes']], ['PR2_Tiana'])
        self.assertEqual([t['nom'] for t in seul['temps_par_tache']], ['Saisie'])
        # Rentabilité < 1 quand l'objectif n'est pas atteint
        self.projet.rendement.valeur = 320
        self.projet.rendement.save()
        moi = next(e for e in self.client.get('/api/rendements/globale/', a).data['employes'] if e['code_barre'] == 'PR00001')
        self.assertEqual(moi['rentabilite'], 0.5)                                        # 160 / 320
        # Pas de plafond : deux fois l'objectif = 2
        self.projet.rendement.valeur = 80
        self.projet.rendement.save()
        moi = next(e for e in self.client.get('/api/rendements/globale/', a).data['employes'] if e['code_barre'] == 'PR00001')
        self.assertEqual(moi['rentabilite'], 2.0)
        # Camembert : seulement les tâches cochées dans Marchés > Tâches
        from rendements.models import ParametresGraphiques
        ParametresGraphiques.actuels().taches_camembert.set([self.controle])
        self.assertEqual([t['nom'] for t in self.client.get('/api/rendements/globale/', a).data['temps_par_tache']], ['Contrôle'])
        # Mois proposés et filtre sur plusieurs mois
        donnees = self.client.get('/api/rendements/globale/', a).data
        mois = self.jour.strftime('%Y-%m')
        self.assertEqual(donnees['mois_disponibles'], [mois])
        self.assertEqual(len(self.client.get('/api/rendements/globale/', {**a, 'mois': f'{mois},2020-01'}).data['employes']), 2)
        self.assertEqual(self.client.get('/api/rendements/globale/', {**a, 'mois': '2020-01'}).data['employes'], [])
        # Période sur la Date de début des lignes
        rien = self.client.get('/api/rendements/globale/', {**a, 'debut': '2030-01-01'}).data
        self.assertEqual(rien['employes'], [])
        self.assertEqual(self.client.get('/api/rendements/globale/exporter/', a).status_code, 200)

    def test_rendement_evolution(self):
        from rendements.models import ParametresGraphiques
        deux = LigneFeuille.objects.get(feuille_id=self.feuille['id'], numero=2)        # Établissements : 40
        self.pointer('08:00', '12:00')                                                   # Saisie, Ménages (100) : 4 h
        self.pointer('13:00', '14:00', tache=self.controle)                              # Contrôle, Ménages : 1 h
        self.pointer('08:00', '10:00', description=deux.description, client=self.client_de('PR2'))   # Saisie, Établissements : 2 h
        reglages = ParametresGraphiques.actuels()
        reglages.courbe1_taches.set([self.production])
        reglages.courbe2_taches.set([self.controle])
        donnees = self.client.get('/api/rendements/evolution/', {'affaires': self.affaire.id}).data
        self.assertEqual(donnees['dates'], [self.jour.isoformat()])
        valeurs = [round(c['valeurs'][0], 2) for c in donnees['courbes']]
        self.assertEqual(valeurs, [186.67, 800.0])                                        # 140 / 6 h × 8 ; 100 / 1 h × 8
        self.assertEqual(donnees['objectif'], 120.0)
        self.assertEqual(self.client.get('/api/rendements/evolution/exporter/', {'affaires': self.affaire.id}).status_code, 200)

    def test_rendement_reel_objectif(self):
        from rendements.models import ParametresGraphiques
        self.pointer('08:00', '12:00')                                                   # Saisie, Ménages (100) : 4 h
        self.pointer('13:00', '15:00', tache=self.controle)                              # Contrôle, Ménages : 2 h
        ParametresGraphiques.actuels().barre1_taches.set([self.production])
        donnees = self.client.get('/api/rendements/reel-objectif/', {'affaires': self.affaire.id}).data
        self.assertEqual([b['objectif'] for b in donnees['barres']], [False, True])     # barre 2 = l'objectif
        moi = donnees['employes'][0]
        self.assertEqual((round(moi['rendement'], 2), moi['objectif'], round(moi['rentabilite'], 2)), (200.0, 120.0, 1.67))
        self.assertEqual(self.client.get('/api/rendements/reel-objectif/exporter/', {'affaires': self.affaire.id}).status_code, 200)

    def test_rendement_evaluation_par_mois(self):
        deux = LigneFeuille.objects.get(feuille_id=self.feuille['id'], numero=2)        # Établissements : 40
        mois_avant = self.jour.replace(day=1) - timedelta(days=3)                         # un jour du mois précédent
        self.pointer('08:00', '12:00')                                                   # moi, Ménages (100) : 4 h ce mois-ci
        self.pointer('08:00', '12:00', jour=mois_avant)                                  # moi, Ménages : 4 h le mois d'avant
        self.pointer('08:00', '10:00', description=deux.description, client=self.client_de('PR2'))   # Tiana : 2 h ce mois-ci
        donnees = self.client.get('/api/rendements/evaluation/', {'affaires': self.affaire.id}).data
        mois = {m['mois']: m for m in donnees['mois']}
        avant, maintenant = mois_avant.strftime('%Y-%m'), self.jour.strftime('%Y-%m')
        self.assertEqual(round(mois[avant]['rendement'], 2), 100.0)                       # moi seul : 100 / 8 h × 8
        self.assertEqual(round(mois[maintenant]['rendement'], 2), 130.0)                  # moyenne (100 ; 160)
        self.assertEqual(mois[maintenant]['employes'][0]['objectifs'][0]['objectif'], 120.0)
        seul = self.client.get('/api/rendements/evaluation/', {'affaires': self.affaire.id, 'employes': self.membre.id}).data
        self.assertEqual([m['mois'] for m in seul['mois']], [maintenant])
        self.assertEqual(self.client.get('/api/rendements/evaluation/exporter/', {'affaires': self.affaire.id}).status_code, 200)

    def test_rendement_analyse_employes(self):
        from marches.models import AffairePrestation, Description, Prestation, Projet, RendementObjectif
        autre = Prestation.objects.create(nom='Contrôle qualité', unite='pages')
        AffairePrestation.objects.create(affaire=self.affaire, prestation=autre)
        projet_b = Projet.objects.create(affaire=self.affaire, prestation=autre, nom='Commune B',
                                         rendement=RendementObjectif.objects.create(prestation=autre, valeur=40), date_livraison='2026-12-31')
        pages = Description.objects.create(projet=projet_b, nom='Pages', quantite=60)
        from gsheets.models import Feuille, PerimetreFeuille
        from gsheets.services import synchroniser
        feuille = Feuille.objects.get(pk=self.feuille['id'])
        PerimetreFeuille.objects.create(feuille=feuille, affaire=self.affaire, prestation=autre)
        synchroniser(feuille)                                                            # Pages entre dans la feuille
        mois_avant = self.jour.replace(day=1) - timedelta(days=3)
        # Prestation A (Saisie, objectif 120) : 6 h le mois d'avant + 6 h ce mois-ci sur Ménages (100) -> 100 / 12 h × 8 = 66,7
        self.pointer('07:30', '13:30', jour=mois_avant)
        self.pointer('07:30', '13:30')
        # Prestation B (Contrôle qualité, objectif 40) : 2 h ce mois-ci sur Pages (60) -> 240 : rentabilité 6
        self.pointer('13:30', '15:30', description=pages)
        ce_mois = self.jour.strftime('%Y-%m')
        donnees = self.client.get('/api/rendements/analyse-employes/', {'employes': self.moi.id, 'mois': ce_mois}).data
        self.assertEqual(donnees['mois'], [ce_mois])
        moi = donnees['employes'][0]
        carte = {c['prestation']: c for c in moi['carte']}
        a, b = carte['Saisie'], carte['Contrôle qualité']
        self.assertEqual((round(a['part'], 2), round(a['rentabilite'], 2), a['zone']), (0.75, 0.56, 'revoir'))
        self.assertEqual((round(b['part'], 2), round(b['rentabilite'], 2), b['zone']), (0.25, 6.0, 'potentiel'))
        self.assertEqual([x['code'] for x in a['badges']], ['adaptation'])          # 2e mois sur la prestation
        self.assertEqual(len(moi['suivi']['mois']), 2)
        # Aucun mois coché : toute la période (6 + 6 h de Saisie, 2 h de Contrôle qualité)
        tous = self.client.get('/api/rendements/analyse-employes/', {'employes': self.moi.id}).data
        self.assertEqual(tous['mois'], [])
        saisie = next(c for c in tous['employes'][0]['carte'] if c['prestation'] == 'Saisie')
        self.assertEqual((saisie['heures'], round(saisie['part'], 3)), (12.0, 0.857))
        # Deux mois cochés : même résultat
        mois_avant_cle = mois_avant.strftime('%Y-%m')
        deux = self.client.get('/api/rendements/analyse-employes/', {'employes': self.moi.id, 'mois': f'{mois_avant_cle},{ce_mois}'}).data
        self.assertEqual(sorted(deux['mois']), sorted([mois_avant_cle, ce_mois]))
        self.assertEqual(next(c for c in deux['employes'][0]['carte'] if c['prestation'] == 'Saisie')['heures'], 12.0)
        # Aide : du temps sur une ligne dont quelqu'un d'autre est l'Employé
        tiana = self.client_de('PR2')
        deux = LigneFeuille.objects.get(feuille_id=self.feuille['id'], numero=2)
        self.pointer('08:00', '10:00', description=deux.description, client=tiana)        # Tiana Employé de Établissements
        self.pointer('15:30', '16:30', description=deux.description, tache=self.controle) # moi : contrôle sur sa ligne
        moi = self.client.get('/api/rendements/analyse-employes/', {'employes': self.moi.id, 'mois': ce_mois}).data['employes'][0]
        self.assertGreater(next(c for c in moi['carte'] if c['prestation'] == 'Saisie')['heures_aide'], 0)
        self.assertEqual(self.client.get('/api/rendements/analyse-employes/exporter/', {'employes': self.moi.id}).status_code, 200)

    def test_mode_donnees_des_feuilles(self):
        """Anciennes données sans pointage : temps et dates lus dans la feuille quand le mode est autorisé et choisi."""
        from rendements.models import ParametresGraphiques
        deux = LigneFeuille.objects.get(feuille_id=self.feuille['id'], numero=2)          # Établissements : 40
        LigneFeuille.objects.filter(pk=self.ligne.pk).update(employe=self.moi, temps_prod=5, controleur=self.membre,
                                                             temps_controle=1, date_debut=self.jour)
        LigneFeuille.objects.filter(pk=deux.pk).update(employe=self.membre, temps_prod=2, date_debut=self.jour)
        a = {'affaires': self.affaire.id}
        f = {**a, 'source': 'feuilles'}
        # Mode non autorisé : on reste sur les pointages (aucun)
        self.assertEqual(self.client.get('/api/rendements/globale/', f).data['employes'][0]['rendement'], None)
        reglages = ParametresGraphiques.actuels()
        reglages.donnees_feuilles = True
        reglages.courbe1_taches.set([self.production])
        reglages.courbe2_taches.set([self.controle])
        reglages.barre1_taches.set([self.production])
        reglages.save()
        donnees = self.client.get('/api/rendements/globale/', f).data
        self.assertEqual(donnees['source'], 'feuilles')
        employes = {e['identifiant']: e for e in donnees['employes']}
        self.assertEqual(round(employes['PR00001_Jean']['rendement'], 2), 160.0)            # 100 / 5 h × 8 (son Temps de prod)
        self.assertEqual({t['nom']: t['heures'] for t in donnees['temps_par_tache']},
                         {'Temps de prod': 7.0, 'Temps de contrôle': 1.0})
        # Filtre Tâches : par type
        controle = self.client.get('/api/rendements/globale/', {**f, 'taches': self.controle.id}).data
        moi = next(e for e in controle['employes'] if e['identifiant'] == 'PR00001_Jean')
        self.assertIsNone(moi['rendement'])                                                  # pas de Temps de contrôle à lui
        # Evolution : tout le temps d'une ligne à sa Date de début
        evolution = self.client.get('/api/rendements/evolution/', f).data
        self.assertEqual(evolution['dates'], [self.jour.isoformat()])
        self.assertEqual(round(evolution['courbes'][0]['valeurs'][0], 2), 160.0)            # 140 / 7 h × 8
        # Réel vs Objectif, Evaluation, Analyse
        reel = self.client.get('/api/rendements/reel-objectif/', f).data
        self.assertEqual(round(reel['employes'][0]['rendement'] or 0, 2) > 0, True)
        evaluation = self.client.get('/api/rendements/evaluation/', f).data
        self.assertEqual([m['mois'] for m in evaluation['mois']], [self.jour.strftime('%Y-%m')])
        analyse = self.client.get('/api/rendements/analyse-employes/', {**f, 'employes': self.membre.id}).data
        carte = analyse['employes'][0]['carte'][0]
        self.assertEqual((carte['heures'], carte['heures_aide']), (3.0, 1.0))               # 2 h à elle + 1 h de contrôle (aide)
        # Sans ?source=feuilles : pointages, comme avant
        self.assertEqual(self.client.get('/api/rendements/globale/', a).data['source'], 'pointages')

    def test_parametres_graphiques(self):
        reponse = self.client.put('/api/rendements/graphiques/', {'courbe1_nom': 'Production'}, format='json')
        self.assertEqual(reponse.status_code, 403)                                       # réservé aux administrateurs
        self.devenir_admin()
        reponse = self.client.put('/api/rendements/graphiques/', {
            'courbe1_nom': 'Production', 'courbe1_couleur': '#1e8a5a', 'courbe1_taches': [self.production.id],
            'taches_camembert': [self.production.id, self.controle.id]}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual((reponse.data['courbe1_couleur'], reponse.data['courbe1_taches']), ('#1E8A5A', [self.production.id]))
        self.assertEqual(self.client.put('/api/rendements/graphiques/', {'courbe2_couleur': 'rouge'}, format='json').status_code, 400)

    def test_rendements_options_et_export(self):
        options = self.client.get('/api/rendements/analyse/options/').data
        self.assertEqual([a['nom'] for a in options['affaires']], ['AF-01 - Recensement'])
        self.assertEqual([p['nom'] for p in options['prestations']], ['Saisie'])
        self.assertEqual(self.client.get('/api/rendements/analyse/exporter/', {'affaires': self.affaire.id}).status_code, 200)

    def test_resume_et_erreurs(self):
        self.pointer('07:30', '16:30', pause=True)
        self.pointer('17:00', '18:00')
        mardi = self.jour + timedelta(days=1)
        resume = self.client.get('/api/pointages/resume/', {'debut': self.jour, 'fin': mardi}).data
        self.assertEqual((resume['nb_lignes'], resume['minutes_normales'], resume['minutes_hs']), (2, 480, 60))
        self.assertEqual([e['date'] for e in resume['erreurs']], [mardi.isoformat()])   # mardi non pointé
        self.assertIn('0 h pointée(s) sur 8 h', resume['erreurs'][0]['message'])

    def test_erreurs_sur_tout_le_temps_pointe(self):
        self.pointer('07:00', '16:00', pause=True)   # 7,5 h de H_Durée + 0,5 h de HS (pause retirée) = 8 h
        resume = self.client.get('/api/pointages/resume/', {'debut': self.jour, 'fin': self.jour}).data
        self.assertEqual(resume['erreurs'], [])
        mardi = self.jour + timedelta(days=1)
        self.pointer('08:00', '12:00', jour=mardi)
        messages = [e['message'] for e in self.client.get('/api/pointages/resume/', {'debut': mardi, 'fin': mardi}).data['erreurs']]
        self.assertTrue(any('4 h pointée(s) sur 8 h' in m for m in messages))
        self.assertTrue(any('pause non cochée' in m for m in messages))

    def test_erreur_pour_aujourd_hui_si_jour_ouvrable(self):
        aujourd_hui = date.today()
        resume = self.client.get('/api/pointages/resume/', {'debut': aujourd_hui, 'fin': aujourd_hui}).data
        attendu = ["Aujourd'hui : 0 h pointée(s) sur 8 h"] if aujourd_hui.weekday() < 5 else []
        self.assertEqual([e['message'] for e in resume['erreurs']], attendu)

    def test_date_de_debut_dans_la_feuille(self):
        mardi = self.jour + timedelta(days=1)
        p_mardi = self.pointer('08:00', '09:00', jour=mardi).data
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.date_debut, mardi)
        p_lundi = self.pointer('08:00', '09:00', tache=self.controle).data   # autre tâche, jour plus tôt
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.date_debut, self.jour)
        self.client.delete(f"/api/pointages/{p_lundi['id']}/")
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.date_debut, mardi)
        self.client.delete(f"/api/pointages/{p_mardi['id']}/")
        self.ligne.refresh_from_db()
        self.assertIsNone(self.ligne.date_debut)

    def importer_pointages(self, lignes, client=None):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from openpyxl import Workbook
        classeur = Workbook()
        for ligne in [['Date', 'H_Début', 'H_Fin', 'Tâche', 'ID description', 'Commentaire', 'Matricule'], *lignes]:
            classeur.active.append(ligne)
        flux = BytesIO()
        classeur.save(flux)
        return (client or self.client).post('/api/pointages/importer/', {'fichier': SimpleUploadedFile('p.xlsx', flux.getvalue())},
                                            format='multipart').data

    def test_un_administrateur_importe_pour_quelqu_un_d_autre(self):
        from django.contrib.auth.models import User
        User.objects.filter(username='PR00001').update(is_superuser=True, is_staff=True)
        jour = self.jour.strftime('%d/%m/%Y')
        rapport = self.importer_pointages([[jour, '08:00', '09:00', 'Saisie', self.ligne.description_id, None, 'PR2']])
        self.assertEqual(rapport['crees'], 1, rapport)
        self.assertIn('PR2_Tiana', rapport['lignes'][0]['libelle'])
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.employe_id, self.membre.id)       # c'est Tiana qui est placée
        # Personne qui n'est pas membre de l'affaire : refusé
        rapport = self.importer_pointages([[jour, '10:00', '11:00', 'Réunion', self.ligne.description_id, None, 'PR3']])
        self.assertEqual(rapport['erreurs'], 1)

    def test_un_non_administrateur_n_importe_que_pour_lui(self):
        jour = self.jour.strftime('%d/%m/%Y')
        rapport = self.importer_pointages([[jour, '08:00', '09:00', 'Saisie', self.ligne.description_id, None, 'PR2']])
        self.assertEqual(rapport['erreurs'], 1)                     # Suivi > Importer : pas dans les droits de base
        self.assertIn('droit d’importer', ' '.join(rapport['lignes'][0]['messages']))
        rapport = self.importer_pointages([[jour, '08:00', '09:00', 'Saisie', self.ligne.description_id, None, 'PR00001']])
        self.assertEqual(rapport['crees'], 1)

    def test_mes_pointages_seulement(self):
        self.pointer('08:00', '09:00')
        autre = self.client_de('PR2')
        self.assertEqual(autre.get('/api/pointages/', {'debut': self.jour, 'fin': self.jour}).data['count'], 0)


class DateDuJourTests(TestCase):
    """« Aujourd'hui » suit le fuseau du .env (Indian/Antananarivo), même si le système est en UTC."""

    def test_aujourdhui_dans_le_fuseau_du_env(self):
        from datetime import datetime, timezone as tz
        from unittest import mock

        from ikarama import temps
        # 22 h 30 UTC le 25 = 1 h 30 le 26 à Madagascar
        fausse_utc = datetime(2026, 11, 25, 22, 30, tzinfo=tz.utc)
        with mock.patch.object(temps, 'datetime', wraps=datetime) as faux:
            faux.now.side_effect = lambda zone=None: fausse_utc.astimezone(zone) if zone else fausse_utc.replace(tzinfo=None)
            self.assertEqual(temps.aujourdhui().isoformat(), '2026-11-26')


class MonTempsAmeliorationsTests(DonneesFeuilleMixin, AuthentifieMixin, TestCase):
    """Quantité modifiée depuis le pointage (avec historique de la feuille) ; pointer pour une autre personne."""
    from pointages.models import Pointage
    from pointages.serializers import nombre_texte as _nombre_texte
    nombre_texte = staticmethod(_nombre_texte)

    def setUp(self):
        super().setUp()
        self.creer()
        self.tache = Tache.objects.create(nom='Saisie', type='PRODUCTION')

    def donnees(self, **autres):
        lundi = date.today() - timedelta(days=date.today().weekday() + 7)
        return {'date': lundi.isoformat(), 'heure_debut': '08:00', 'heure_fin': '10:00', 'descriptions': [self.d1.id],
                'tache': self.tache.id, **autres}

    def test_quantite_modifiee_avec_historique(self):
        from gsheets.models import HistoriqueLigne
        avant = self.d1.quantite
        reponse = self.client.post('/api/pointages/', self.donnees(quantites={str(self.d1.id): '6500'}), format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.d1.refresh_from_db()
        self.assertEqual(self.d1.quantite, 6500)
        h = HistoriqueLigne.objects.get(champ='quantite')
        self.assertEqual((h.libelle, h.nouvelle_valeur, h.auteur.code_barre), ('Quantité', '6500', 'PR00001'))
        self.assertEqual(h.ancienne_valeur, self.nombre_texte(avant))
        # Arborescence : quantité modifiable (droit de base, membre de l'affaire)
        arbre = self.client.get('/api/pointages/arborescence/', {'affaire': self.affaire.id}).data
        self.assertTrue(arbre['prestations'][0]['projets'][0]['descriptions'][0]['quantite_modifiable'])

    def test_quantite_refusee_hors_droit_et_pointage_annule(self):
        from autorisations.models import AttributionRole, DroitRole, Role
        role = Role.objects.create(nom='Sans quantité')
        DroitRole.objects.create(role=role, module='pointages_quantite', action='modifier', perimetre='TOUTES', effet='REFUSER')
        AttributionRole.objects.create(role=role, critere='MATRICULE', employe=self.moi)
        reponse = self.client.post('/api/pointages/', self.donnees(quantites={str(self.d1.id): '1'}), format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertFalse(self.Pointage.objects.exists())          # tout ou rien

    def test_pointer_pour_une_autre_personne(self):
        reponse = self.client.post(f'/api/pointages/?employe={self.membre.id}', self.donnees(), format='json')
        self.assertEqual(reponse.status_code, 403)                # sans le droit Modifier du Suivi
        from autorisations.models import AttributionRole, DroitRole, Role
        role = Role.objects.create(nom='Suivi')
        DroitRole.objects.create(role=role, module='pointages_suivi', action='modifier', perimetre='TOUS')
        AttributionRole.objects.create(role=role, critere='MATRICULE', employe=self.moi)
        reponse = self.client.post(f'/api/pointages/?employe={self.membre.id}', self.donnees(), format='json')
        self.assertEqual((reponse.status_code, reponse.data['employe']), (201, self.membre.id))
