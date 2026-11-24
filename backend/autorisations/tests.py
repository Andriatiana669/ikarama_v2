# backend/autorisations/tests.py
"""Lancer : python manage.py test autorisations"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from authentification.tests import AuthentifieMixin, jeton_keycloak
from rest_framework.test import APIClient
from utilisateurs.models import Employe, EmployePoste

from .models import RegleAcces


def employe(code, nom, pole, chef=None, poste='Opérateur'):
    e = Employe.objects.create(code_barre=code, nom=nom, prenom=nom, chef=chef)
    EmployePoste.objects.create(employe=e, pole=pole, poste_nom=poste)
    return e


class AccesSiteTests(AuthentifieMixin, TestCase):
    """
    Moi = PR00001, administrateur, pôle A.
        Chef (pôle B) ── Paul (pôle B) ── Zoé (pôle B)
    """

    def setUp(self):
        super().setUp()
        self.moi = employe('PR00001', 'Moi', 'A')
        self.client.get('/api/auth/moi/')   # rattache le compte à la fiche
        User.objects.filter(username='PR00001').update(is_staff=True, is_superuser=True)
        self.chef = employe('PR10', 'Chef', 'B')
        self.paul = employe('PR11', 'Paul', 'B', chef=self.chef)
        self.zoe = employe('PR12', 'Zoe', 'B', chef=self.paul)

    def client_de(self, matricule):
        jeton = jeton_keycloak(matricule.lower())
        self.jetons_valides.add(jeton)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {jeton}')
        return client

    def regle(self, **champs):
        return RegleAcces.objects.create(**champs)

    def codes_visibles(self):
        return {e['code_barre'] for e in self.client.get('/api/utilisateurs/').data['results']}

    # --- Règles -------------------------------------------------------
    def test_sans_regle_tout_le_monde_entre(self):
        self.assertEqual(self.client_de('PR11').get('/api/utilisateurs/').status_code, 200)

    def test_autoriser_un_pole(self):
        self.regle(critere='POLE', pole='A')
        self.assertEqual(self.client.get('/api/utilisateurs/').status_code, 200)
        reponse = self.client_de('PR11').get('/api/utilisateurs/')
        self.assertEqual(reponse.status_code, 403)
        self.assertEqual(reponse.data['code'], 'acces_refuse')

    def test_moi_indique_le_refus_sans_erreur(self):
        self.regle(critere='POLE', pole='A')
        donnees = self.client_de('PR11').get('/api/auth/moi/').data
        self.assertFalse(donnees['acces_site'])
        self.assertIsNone(donnees['employe'])

    def test_exception_par_matricule(self):
        self.regle(critere='POLE', pole='A')
        self.regle(critere='MATRICULE', employe=self.paul)
        self.assertEqual(self.client_de('PR11').get('/api/utilisateurs/').status_code, 200)

    def test_refus_l_emporte(self):
        self.regle(critere='POLE', pole='B')
        self.regle(critere='POLE', pole='A')
        self.regle(effet='REFUSER', critere='MATRICULE', employe=self.paul)
        self.assertEqual(self.client_de('PR11').get('/api/utilisateurs/').status_code, 403)
        self.assertEqual(self.client_de('PR12').get('/api/utilisateurs/').status_code, 200)

    def test_n1_direct_ou_hierarchie(self):
        self.regle(critere='POLE', pole='A')
        regle = self.regle(critere='N1', employe=self.chef, portee='DIRECT')
        self.assertEqual(self.client_de('PR11').get('/api/utilisateurs/').status_code, 200)   # Paul : direct
        self.assertEqual(self.client_de('PR12').get('/api/utilisateurs/').status_code, 403)   # Zoé : N-2
        regle.portee = 'HIERARCHIE'
        regle.save()
        self.assertEqual(self.client_de('PR12').get('/api/utilisateurs/').status_code, 200)
        self.assertEqual(self.client_de('PR10').get('/api/utilisateurs/').status_code, 403)   # le N+1 lui-même

    def test_superadmin_soumis_aux_regles(self):
        self.regle(critere='POLE', pole='B')
        self.assertEqual(self.client.get('/api/utilisateurs/').status_code, 403)
        self.assertEqual(self.client.post('/api/auth/session-admin/').status_code, 403)

    # --- Visibilité ---------------------------------------------------
    def test_personnes_sans_acces_masquees(self):
        self.regle(critere='POLE', pole='A')
        self.assertEqual(self.codes_visibles(), {'PR00001'})
        self.assertEqual(self.client.get('/api/equipes/organigramme/').data[0]['code_barre'], 'PR00001')

    def test_n1_masque_dans_la_fiche(self):
        self.regle(critere='POLE', pole='B')
        self.regle(critere='MATRICULE', employe=self.moi)
        self.regle(effet='REFUSER', critere='MATRICULE', employe=self.paul)
        zoe = self.client.get(f'/api/utilisateurs/{self.zoe.pk}/').data
        self.assertIsNone(zoe['chef'])   # Paul, son N+1, n'a pas accès

    def test_acces_retire_reste_visible(self):
        Employe.objects.filter(pk=self.paul.pk).update(premiere_connexion=timezone.now())
        self.regle(critere='POLE', pole='A')
        self.assertEqual(self.codes_visibles(), {'PR00001', 'PR11'})
        paul = next(e for e in self.client.get('/api/utilisateurs/').data['results'] if e['code_barre'] == 'PR11')
        self.assertEqual(paul['statut_acces'], 'RETIRE')

    def test_premiere_connexion_enregistree(self):
        self.client_de('PR11').get('/api/auth/moi/')
        self.assertIsNotNone(Employe.objects.get(pk=self.paul.pk).premiere_connexion)

    def test_organigramme_saute_un_responsable_masque(self):
        # Paul n'a pas accès ; Zoé (sa collaboratrice) remonte sous le Chef
        self.regle(critere='MATRICULE', employe=self.moi)
        self.regle(critere='MATRICULE', employe=self.chef)
        self.regle(critere='MATRICULE', employe=self.zoe)
        arbre = {n['code_barre']: n for n in self.client.get('/api/equipes/organigramme/').data}
        self.assertEqual([e['code_barre'] for e in arbre['PR10']['enfants']], ['PR12'])

    # --- Page Paramètres ----------------------------------------------
    def test_perte_de_son_propre_acces_demande_confirmation(self):
        donnees = {'effet': 'AUTORISER', 'critere': 'POLE', 'pole': 'B'}
        reponse = self.client.post('/api/autorisations/regles/', donnees)
        self.assertEqual(reponse.status_code, 409)
        self.assertEqual(RegleAcces.objects.count(), 0)   # rien n'a été enregistré
        self.assertEqual(self.client.post('/api/autorisations/regles/?confirmer=1', donnees).status_code, 201)

    def test_validation_du_critere(self):
        reponse = self.client.post('/api/autorisations/regles/', {'critere': 'MATRICULE'})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('employe', reponse.data['erreurs'])

    def test_recherche_parmi_tous_les_employes(self):
        self.regle(critere='POLE', pole='A')
        trouves = self.client.get('/api/autorisations/acces/employes/', {'search': 'paul'}).data
        self.assertEqual([e['code_barre'] for e in trouves], ['PR11'])   # visible ici, même sans accès

    def test_pages_parametres_reservees_aux_administrateurs(self):
        self.assertEqual(self.client_de('PR11').get('/api/autorisations/regles/').status_code, 403)


# ======================================================================
# Paramètres > Autorisation : droits de base, rôles (autoriser / refuser), périmètres, API
# ======================================================================
from datetime import date as _date, timedelta as _timedelta  # noqa: E402

from django.contrib.auth.models import User as _User  # noqa: E402

from gsheets.tests import DonneesFeuilleMixin  # noqa: E402
from marches.models import Tache  # noqa: E402
from utilisateurs.models import EmployePoste  # noqa: E402

from .models import AttributionRole, DroitRole, Role  # noqa: E402


class RolesTests(DonneesFeuilleMixin, AuthentifieMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.tache = Tache.objects.create(nom='Saisie', type='PRODUCTION')
        self.jour = _date.today() - _timedelta(days=(_date.today().weekday() + 7))
        self.feuille = self.creer().data

    def periode(self):
        return {'debut': self.jour.isoformat(), 'fin': self.jour.isoformat()}

    def pointer(self, client):
        return client.post('/api/pointages/', {
            'date': self.jour.isoformat(), 'heure_debut': '08:00', 'heure_fin': '09:00',
            'descriptions': [self.d1.id], 'tache': self.tache.id}, format='json')

    def role(self, nom, droits, attribuer_a):
        role = Role.objects.create(nom=nom)
        for d in droits:
            DroitRole.objects.create(role=role, **d)
        AttributionRole.objects.create(role=role, critere='MATRICULE', employe=attribuer_a)
        return role

    def devenir_admin(self):
        _User.objects.filter(username='PR00001').update(is_staff=True, is_superuser=True)

    # --- Droits de base ---------------------------------------------------
    def test_droits_de_base_dans_moi(self):
        moi = self.client.get('/api/auth/moi/').data                 # responsable (+ rôle « Gestion des feuilles » des tests)
        self.assertTrue(moi['est_responsable'])
        self.assertEqual(moi['autorisations']['pointages_suivi'], [])          # Suivi : seulement par un rôle
        self.assertEqual(moi['autorisations']['pointages_verification'], [])   # Vérification : idem
        self.assertIn('voir', moi['autorisations']['marches_taches'])            # par le rôle de test
        tiana = self.client_de('PR2').get('/api/auth/moi/').data
        self.assertFalse(tiana['est_responsable'])
        self.assertEqual(tiana['autorisations']['gsheets_feuilles'], ['voir'])  # voir ses affaires, rien d'autre
        for module in ('marches_affaires', 'marches_prestations', 'marches_projets', 'marches_descriptions',
                       'marches_taches', 'marches_statuts', 'marches_archives'):
            self.assertEqual(tiana['autorisations'][module], [], module)

    def test_responsable_sans_suivi_ni_verification(self):
        periode = self.periode()
        self.assertEqual(self.client.get('/api/pointages/tous/', periode).status_code, 403)
        self.assertEqual(self.client.get('/api/pointages/verification/', periode).status_code, 403)
        self.assertNotIn('equipe', self.client.get('/api/accueil/').data)

    def test_verification_et_mon_equipe_par_un_role(self):
        from datetime import date
        lundi = date.today() - _timedelta(days=date.today().weekday())
        self.role('Chef d’équipe', [{'module': 'pointages_verification', 'action': 'voir', 'perimetre': 'MEMBRES_AFFAIRES'}], self.moi)
        accueil = self.client.get('/api/accueil/').data
        self.assertEqual(accueil['equipe']['periode']['debut'], lundi.isoformat())          # semaine en cours
        self.assertEqual(accueil['equipe']['periode']['fin'], (lundi + _timedelta(days=6)).isoformat())
        self.assertEqual(accueil['equipe']['nb_equipe'], 1)                                   # Tiana, membre de mon affaire
        self.assertEqual(self.client.get('/api/pointages/verification/', self.periode()).status_code, 200)
        self.assertEqual(self.client.get('/api/pointages/verification/exporter/', {**self.periode(), 'colonnes': '[{"cle":"date","libelle":"Date"}]'}).status_code, 403)

    def test_mes_feuilles_sans_role(self):
        tiana = self.client_de('PR2')
        self.assertEqual(len(tiana.get('/api/gsheets/feuilles/').data['results']), 1)     # voir : ses affaires
        feuille = tiana.get('/api/gsheets/feuilles/').data['results'][0]
        self.assertEqual(feuille['droits'], {'modifier': False, 'supprimer': False, 'importer_donnees': False})
        self.assertEqual(tiana.get('/api/gsheets/feuilles/exporter/', {'colonnes': '[{"cle":"nom","libelle":"Nom"}]'}).status_code, 403)
        self.assertEqual(tiana.get('/api/gsheets/lignes/', {'feuille': feuille['id']}).status_code, 200)   # ses données : oui

    def test_marche_sans_role_mes_marches_en_consultation(self):
        tiana = self.client_de('PR2')                                   # membre de l'affaire, sans rôle
        self.assertEqual(tiana.get('/api/marches/affaires/').status_code, 403)                     # Ajouter un marché
        self.assertEqual(len(tiana.get('/api/marches/affaires/', {'mes': 1}).data['results']), 1)  # Mes marchés : oui
        self.assertEqual(len(tiana.get('/api/marches/projets/', {'affaire': self.affaire.id}).data['results']), 1)
        self.assertEqual(len(tiana.get('/api/marches/prestations/', {'affaire': self.affaire.id}).data['results']), 1)
        self.assertEqual(tiana.get('/api/marches/taches/').status_code, 403)                       # même Voir
        self.assertEqual(tiana.get('/api/marches/statuts/').status_code, 403)
        self.assertEqual(tiana.post('/api/marches/projets/', {'affaire': self.affaire.id, 'nom': 'X'}).status_code, 403)
        mamy = self.client_de('PR3')                                    # étrangère à l'affaire
        self.assertEqual(len(mamy.get('/api/marches/projets/', {'affaire': self.affaire.id}).data['results']), 0)

    def test_equipe_de_et_plusieurs_perimetres(self):
        from utilisateurs.models import Employe
        jean = Employe.objects.create(code_barre='PR50', nom='Jean', prenom='Jean')
        chef = Employe.objects.create(code_barre='PR51', nom='Chef', prenom='Chef', chef=jean)
        self.membre.chef = chef                                         # Tiana : sous Chef, sous Jean
        self.membre.save()
        self.pointer(self.client_de('PR2'))
        mamy = self.client_de('PR3')
        self.role('Équipe de Jean', [
            {'module': 'pointages_suivi', 'action': 'voir', 'perimetre': 'EQUIPE_DE', 'employe': jean},
            {'module': 'pointages_suivi', 'action': 'voir', 'perimetre': 'PERSONNE', 'employe': self.moi},   # 2e périmètre
        ], self.etranger)
        lignes = mamy.get('/api/pointages/tous/', self.periode()).data['results']
        self.assertEqual([l['employe_details']['code_barre'] for l in lignes], ['PR2'])            # toute la hiérarchie
        self.role('Affaires de l’équipe de Jean', [
            {'module': 'marches_affaires', 'action': 'voir', 'perimetre': 'EQUIPE_DE', 'employe': jean}], self.etranger)
        noms = [a['nom'] for a in mamy.get('/api/marches/affaires/').data['results']]
        self.assertEqual(noms, ['Recensement'])                         # Tiana (équipe de Jean) en est membre

    # --- Rôles : autoriser ------------------------------------------------
    def test_role_qui_donne_le_suivi_de_tout_le_monde(self):
        self.pointer(self.client_de('PR2'))
        mamy = self.client_de('PR3')                                    # ni responsable ni membre
        self.assertEqual(mamy.get('/api/pointages/tous/', self.periode()).status_code, 403)
        self.role('RH lecture', [{'module': 'pointages_suivi', 'action': 'voir', 'perimetre': 'TOUS'}], self.etranger)
        reponse = mamy.get('/api/pointages/tous/', self.periode())
        self.assertEqual(reponse.status_code, 200, reponse.data)
        lignes = reponse.data['results']
        self.assertEqual([l['employe_details']['code_barre'] for l in lignes], ['PR2'])
        self.assertEqual(mamy.get('/api/pointages/tous/exporter/', self.periode()).status_code, 403)              # pas « Exporter »
        self.assertEqual(mamy.delete(f"/api/pointages/tous/{lignes[0]['id']}/").status_code, 403)

    def test_attribution_par_pole(self):
        EmployePoste.objects.create(employe=self.etranger, pole='RH', poste_nom='Gestionnaire')
        role = Role.objects.create(nom='RH')
        DroitRole.objects.create(role=role, module='marches_affaires', action='voir', perimetre='TOUTES')
        AttributionRole.objects.create(role=role, critere='POLE', pole='rh')
        self.assertEqual(self.client_de('PR3').get('/api/marches/affaires/').status_code, 200)

    # --- Rôles : refuser (retirer un droit de base) ---------------------------
    def test_refus_total_retire_un_droit_de_base(self):
        self.role('Sans création de feuille', [
            {'module': 'gsheets_feuilles', 'action': 'creer', 'perimetre': 'TOUTES', 'effet': 'REFUSER'}], self.moi)
        reponse = self.client.get('/api/gsheets/feuilles/affaires-disponibles/')
        self.assertEqual(reponse.status_code, 403)
        self.assertIn('Créer', reponse.data['detail'])

    def test_refus_partiel_retire_une_personne_du_perimetre(self):
        p = self.pointer(self.client_de('PR2'))
        self.assertEqual(p.status_code, 201, p.data)
        self.role('Suivi de mes affaires', [{'module': 'pointages_suivi', 'action': 'voir', 'perimetre': 'MEMBRES_AFFAIRES'}], self.moi)
        self.assertEqual(len(self.client.get('/api/pointages/tous/', self.periode()).data['results']), 1)
        self.role('Pas Tiana', [{'module': 'pointages_suivi', 'action': 'voir', 'perimetre': 'PERSONNE',
                                 'employe': self.membre, 'effet': 'REFUSER'}], self.moi)
        self.assertEqual(len(self.client.get('/api/pointages/tous/', self.periode()).data['results']), 0)

    def test_role_inactif_sans_effet(self):
        role = self.role('Inactif', [{'module': 'pointages_suivi', 'action': 'voir', 'perimetre': 'TOUS'}], self.etranger)
        role.actif = False
        role.save()
        self.assertEqual(self.client_de('PR3').get('/api/pointages/tous/', self.periode()).status_code, 403)

    # --- API de Paramètres > Autorisation ---------------------------------------
    def test_api_reservee_aux_superadmins(self):
        self.assertEqual(self.client.get('/api/autorisations/roles/').status_code, 403)
        self.assertEqual(self.client.get('/api/autorisations/catalogue/').status_code, 403)

    def test_api_roles_grille_attributions_tester_journal(self):
        self.devenir_admin()
        catalogue = self.client.get('/api/autorisations/catalogue/').data
        suivi = next(m for m in catalogue['modules'] if m['code'] == 'pointages_suivi')
        self.assertIsNone(suivi['base']['voir'])                                            # seulement par un rôle
        role = self.client.post('/api/autorisations/roles/', {'nom': 'Chef d’équipe', 'description': 'N+1'}).data
        grille = self.client.put(f"/api/autorisations/roles/{role['id']}/droits/", {'droits': [
            {'module': 'pointages_suivi', 'action': 'voir', 'perimetre': 'DIRECT'},
            {'module': 'pointages_suivi', 'action': 'supprimer', 'perimetre': 'DIRECT', 'effet': 'REFUSER'},
        ]}, format='json')
        self.assertEqual((grille.status_code, len(grille.data['droits'])), (200, 2))
        invalide = self.client.put(f"/api/autorisations/roles/{role['id']}/droits/", {'droits': [
            {'module': 'pointages_suivi', 'action': 'archiver', 'perimetre': 'TOUS'}]}, format='json')
        self.assertEqual(invalide.status_code, 400)                                               # action impossible
        self.etranger.chef = None
        self.membre.chef = self.etranger
        self.membre.save()
        attribution = self.client.post('/api/autorisations/attributions/', {
            'role': role['id'], 'critere': 'MATRICULE', 'employe': self.etranger.id}, format='json')
        self.assertEqual(attribution.status_code, 201)
        personnes = self.client.get(f"/api/autorisations/roles/{role['id']}/personnes/").data
        self.assertEqual(personnes['nombre'], 1)
        test = self.client.post('/api/autorisations/tester/', {
            'employe': self.etranger.id, 'module': 'pointages_suivi', 'action': 'voir', 'cible_employe': self.membre.id},
            format='json').data
        self.assertTrue(test['autorise'])
        self.assertEqual(test['roles'], ['Chef d’équipe'])
        refus = self.client.post('/api/autorisations/tester/', {
            'employe': self.etranger.id, 'module': 'pointages_suivi', 'action': 'supprimer'}, format='json').data
        self.assertFalse(refus['autorise'])
        journal = self.client.get('/api/autorisations/journal/').data
        self.assertTrue(any('Chef d’équipe' in l['texte'] for l in journal))
        self.assertEqual(len(journal), 3)                                    # création, grille, attribution


class ControlesEtSourcesTests(DonneesFeuilleMixin, AuthentifieMixin, TestCase):
    """Contrôles de cohérence par un rôle ; affaire « Pointage seulement » ; source « Données des pointages »."""

    def setUp(self):
        super().setUp()
        self.tache = Tache.objects.create(nom='Saisie', type='PRODUCTION')

    def test_controles_par_un_role(self):
        tiana = self.client_de('PR2')
        self.assertEqual(tiana.get('/api/controles/').status_code, 403)
        role = Role.objects.create(nom='Qualité des données')
        DroitRole.objects.create(role=role, module='parametres_controles', action='voir', perimetre='TOUS')
        AttributionRole.objects.create(role=role, critere='MATRICULE', employe=self.membre)
        self.assertEqual(tiana.get('/api/controles/').status_code, 200)
        self.assertIn('administrateur', tiana.get('/api/accueil/').data)

    def test_pointage_seul_et_source_pointages(self):
        from marches.models import Description
        from rendements.models import ParametresGraphiques
        # Une description pointée mais hors de toute feuille
        hors = Description.objects.create(projet=self.projet, nom='Hors feuille', quantite=80)
        from gsheets.models import LigneFeuille
        LigneFeuille.objects.filter(description=hors).delete()
        self.client_de('PR2').post('/api/pointages/', {'date': (_date.today() - _timedelta(days=_date.today().weekday() + 7)).isoformat(),
                                                       'heure_debut': '08:00', 'heure_fin': '12:00', 'descriptions': [hors.id],
                                                       'tache': self.tache.id}, format='json')
        LigneFeuille.objects.filter(description=hors).delete()     # le pointage ne la recrée pas : elle reste hors feuille
        _User.objects.filter(username='PR00001').update(is_staff=True, is_superuser=True)
        controle = lambda: next(c for c in self.client.get('/api/controles/').data['controles'] if c['code'] == 'description_hors_feuille')
        self.assertEqual(controle()['nombre'], 1)
        self.affaire.pointage_seul = True
        self.affaire.save()
        self.assertEqual(controle()['nombre'], 0)                 # affaire « Pointage seulement » : plus signalée
        # Rendement, source « Données des pointages » : la description hors feuille compte, attribuée à Tiana
        reglages = ParametresGraphiques.actuels()
        reglages.donnees_pointages = True
        reglages.save()
        donnees = self.client.get('/api/rendements/globale/', {'source': 'pointages'}).data
        self.assertEqual(donnees['source'], 'pointages_seuls')
        tiana = next(e for e in donnees['employes'] if e['code_barre'] == 'PR2')
        self.assertEqual(round(tiana['rendement'], 2), 160.0)    # 80 / 4 h × 8
        # Le temps d'une autre personne sur cette description ne compte pas (seulement celui de Tiana)
        self.client.post('/api/pointages/', {'date': (_date.today() - _timedelta(days=_date.today().weekday() + 6)).isoformat(),
                                             'heure_debut': '08:00', 'heure_fin': '09:00', 'descriptions': [hors.id],
                                             'tache': self.tache.id}, format='json')
        LigneFeuille.objects.filter(description=hors).delete()
        donnees = self.client.get('/api/rendements/globale/', {'source': 'pointages'}).data
        self.assertEqual(round(next(e for e in donnees['employes'] if e['code_barre'] == 'PR2')['rendement'], 2), 160.0)
        self.assertEqual(sum(t['heures'] for t in donnees['temps_par_tache']), 4.0)
        # Graphiques en heures pointées : Globale (heures de Tiana) et Evaluation (heures par mois)
        self.assertEqual(next(e for e in donnees['employes'] if e['code_barre'] == 'PR2')['heures'], 4.0)
        evaluation = self.client.get('/api/rendements/evaluation/', {'source': 'pointages'}).data
        self.assertEqual(sum(m['heures'] for m in evaluation['mois']), 4.0)
        normal = self.client.get('/api/rendements/globale/').data
        self.assertFalse(any(e['code_barre'] == 'PR2' and e['rendement'] for e in normal['employes']))
