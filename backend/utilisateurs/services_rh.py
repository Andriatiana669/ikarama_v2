# backend/utilisateurs/services_rh.py
"""
Synchronisation des employés avec l'API RH externe.

Deux usages, une seule logique :
  - synchroniser_tous()          : bouton « Synchroniser » de la page Utilisateurs ;
  - declencher_a_la_connexion()  : mise à jour de SA fiche quand on ouvre l'application
                                   (au plus une fois toutes les N heures, en arrière-plan).

Format attendu d'un employé dans l'API RH (repris d'Alimanaka) :
    {"id", "codeBarre", "nom", "prenom", "prenomUsuel", "sexe", "email", "chef",
     "employePoste": {...} ou [{...}]  avec  {"poleID", "pole", "poste": {"nom", "statut"}}}
"""
import logging
import threading
import time

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import close_old_connections, transaction
from django.utils import timezone

from ikarama.reseau import decrire_erreur_reseau

from .models import Employe, EmployePoste

logger = logging.getLogger(__name__)

CLE_LISTE = 'api_rh_employes'   # liste gardée settings.DUREE_CACHE_API_RH secondes (0 = jamais)
CLE_JETON_SERVICE = 'api_rh_jeton_service'


class ApiRhIndisponible(Exception):
    """L'API RH n'a pas pu être lue (réseau, droits, configuration)."""


# ------------------------------------------------------------------
# Lecture de l'API RH
# ------------------------------------------------------------------
def obtenir_jeton_service():
    """Jeton du compte de service Keycloak (flux client_credentials), gardé en cache."""
    jeton = cache.get(CLE_JETON_SERVICE)
    if jeton:
        return jeton
    conf = settings.EXTERNAL_API_KEYCLOAK
    if not (conf['SERVER_URL'] and conf['REALM'] and conf['CLIENT_ID'] and conf['CLIENT_SECRET']):
        return None
    url = f"{conf['SERVER_URL']}/realms/{conf['REALM']}/protocol/openid-connect/token"
    try:
        reponse = requests.post(url, data={
            'grant_type': 'client_credentials',
            'client_id': conf['CLIENT_ID'],
            'client_secret': conf['CLIENT_SECRET'],
        }, verify=settings.CA_BUNDLE, timeout=15)
    except requests.RequestException as exc:
        logger.error("Compte de service Keycloak injoignable (%s) : %s", url, decrire_erreur_reseau(exc))
        return None
    if reponse.status_code != 200:
        logger.warning("Compte de service Keycloak : réponse %s", reponse.status_code)
        return None
    donnees = reponse.json()
    jeton = donnees.get('access_token')
    if jeton:
        # On le garde un peu moins longtemps que sa durée de vie réelle
        cache.set(CLE_JETON_SERVICE, jeton, max(30, int(donnees.get('expires_in', 300)) - 30))
    return jeton


def lire_employes_externes(jeton_utilisateur=None, utiliser_cache=True):
    """
    Liste des employés de l'API RH. Lève ApiRhIndisponible en cas d'échec.
    La liste est gardée DUREE_CACHE_API_RH secondes pour ne pas surcharger l'API RH.
    """
    duree_cache = settings.DUREE_CACHE_API_RH
    if utiliser_cache and duree_cache > 0:
        en_cache = cache.get(CLE_LISTE)
        if en_cache is not None:
            logger.info("API RH : liste réutilisée (lue il y a %s s)", int(time.time() - en_cache['lue_a']))
            return en_cache['donnees']
    url = settings.EXTERNAL_API_EMPLOYE_URL
    if not url:
        raise ApiRhIndisponible("EXTERNAL_API_EMPLOYE_URL n'est pas configurée.")

    dernier_statut = None
    for jeton in (jeton_utilisateur, obtenir_jeton_service()):
        if not jeton:
            continue
        try:
            reponse = requests.get(
                url,
                headers={'Authorization': f'Bearer {jeton}', 'Accept': 'application/json'},
                verify=settings.CA_BUNDLE,
                timeout=30,
            )
        except requests.RequestException as exc:
            logger.error("API RH injoignable (%s) : %s", url, decrire_erreur_reseau(exc))
            raise ApiRhIndisponible("API RH injoignable.") from exc
        dernier_statut = reponse.status_code
        if reponse.status_code == 200:
            donnees = reponse.json()
            if not isinstance(donnees, list):
                raise ApiRhIndisponible("Format de réponse inattendu de l'API RH.")
            if duree_cache > 0:
                cache.set(CLE_LISTE, {'lue_a': time.time(), 'donnees': donnees}, duree_cache)
            logger.info("API RH : liste lue (%s employés)", len(donnees))
            return donnees
    raise ApiRhIndisponible(
        f"L'API RH a refusé la demande (code {dernier_statut})." if dernier_statut
        else "Aucun jeton disponible pour interroger l'API RH."
    )


# ------------------------------------------------------------------
# Application des données sur une fiche
# ------------------------------------------------------------------
def _postes_depuis(emp_data):
    postes = emp_data.get('employePoste') or []
    postes = [postes] if isinstance(postes, dict) else postes
    return [p for p in postes if isinstance(p, dict)]


@transaction.atomic
def appliquer_donnees(employe, emp_data, lier_chef=True):
    """Met à jour une fiche avec les données RH. Retourne la liste des champs modifiés."""
    modifies = []
    valeurs = {
        'external_id': emp_data.get('id'),
        'civilite': emp_data.get('sexe') or emp_data.get('CIVILITE') or employe.civilite,
        'nom': emp_data.get('nom') or employe.nom,
        'prenom': emp_data.get('prenom') or employe.prenom,
        'prenom_usuel': emp_data.get('prenomUsuel') or employe.prenom_usuel,
        'email': emp_data.get('email') or employe.email,
    }
    for champ, valeur in valeurs.items():
        if valeur is None or getattr(employe, champ) == valeur:
            continue
        if champ == 'external_id' and Employe.objects.filter(external_id=valeur).exclude(pk=employe.pk).exists():
            logger.warning("external_id %s déjà utilisé par une autre fiche", valeur)
            continue
        setattr(employe, champ, valeur)
        modifies.append(champ)

    if lier_chef and emp_data.get('chef'):
        chef = Employe.objects.filter(external_id=emp_data['chef']).exclude(pk=employe.pk).first()
        if chef and employe.chef_id != chef.id:
            employe.chef = chef
            modifies.append('chef')

    # Compte Django : lié par le matricule
    if not employe.user_id and employe.code_barre:
        user = User.objects.filter(username__iexact=employe.code_barre, employe__isnull=True).first()
        if user:
            employe.user = user
            modifies.append('user')

    employe.derniere_synchro = timezone.now()
    employe.save(update_fields=modifies + ['derniere_synchro'])

    # Postes : remplacés seulement s'ils ont changé
    postes = _postes_depuis(emp_data)
    if postes:
        nouveaux = sorted(
            (str(p.get('poleID')), p.get('pole') or '', (p.get('poste') or {}).get('nom') or '',
             (p.get('poste') or {}).get('statut') or '')
            for p in postes
        )
        actuels = sorted(
            (str(a), b or '', c or '', d or '')
            for a, b, c, d in employe.postes.values_list('pole_id', 'pole', 'poste_nom', 'poste_statut')
        )
        if nouveaux != actuels:
            employe.postes.all().delete()
            EmployePoste.objects.bulk_create([
                EmployePoste(
                    employe=employe,
                    pole_id=p.get('poleID'),
                    pole=p.get('pole') or '',
                    poste_nom=(p.get('poste') or {}).get('nom') or '',
                    poste_statut=(p.get('poste') or {}).get('statut') or '',
                ) for p in postes
            ])
            modifies.append('postes')

    # Nom et email du compte Django
    if employe.user:
        champs_user = []
        for champ, valeur in (('first_name', employe.prenom), ('last_name', employe.nom),
                              ('email', emp_data.get('email'))):
            if valeur and getattr(employe.user, champ) != valeur:
                setattr(employe.user, champ, valeur)
                champs_user.append(champ)
        if champs_user:
            employe.user.save(update_fields=champs_user)
    return modifies


# ------------------------------------------------------------------
# Synchronisation complète
# ------------------------------------------------------------------
def synchroniser_tous(jeton_utilisateur=None):
    """
    Crée / met à jour toutes les fiches depuis l'API RH, puis relie les responsables.
    Retourne un résumé {'total', 'crees', 'mis_a_jour', 'chefs_lies', 'erreurs'}.
    """
    donnees = lire_employes_externes(jeton_utilisateur, utiliser_cache=False)
    resume = {'total': len(donnees), 'crees': 0, 'mis_a_jour': 0, 'chefs_lies': 0, 'erreurs': []}

    # 1re passe : fiches (sans les responsables, qui n'existent peut-être pas encore)
    for emp_data in donnees:
        code = str(emp_data.get('codeBarre') or '').strip()
        if not code:
            continue
        try:
            employe = Employe.objects.filter(code_barre__iexact=code).first()
            cree = employe is None
            if cree:
                employe = Employe.objects.create(
                    code_barre=code, nom=emp_data.get('nom') or '', prenom=emp_data.get('prenom') or '',
                )
            modifies = appliquer_donnees(employe, emp_data, lier_chef=False)
            if cree:
                resume['crees'] += 1
            elif modifies:
                resume['mis_a_jour'] += 1
        except Exception:   # une fiche en erreur ne bloque pas les autres
            logger.exception("Synchro RH : erreur sur %s", code)
            resume["erreurs"].append(f"{code} : enregistrement impossible (voir le journal)")

    # 2e passe : responsables (N+1)
    par_external_id = dict(Employe.objects.exclude(external_id=None).values_list('external_id', 'id'))
    for emp_data in donnees:
        code, chef_externe = str(emp_data.get('codeBarre') or '').strip(), emp_data.get('chef')
        chef_id = par_external_id.get(chef_externe) if chef_externe else None
        if code and chef_id:
            resume['chefs_lies'] += Employe.objects.filter(
                code_barre__iexact=code).exclude(chef_id=chef_id).exclude(pk=chef_id).update(chef_id=chef_id)

    cache.delete(CLE_LISTE)
    logger.info("Synchro RH complète : %s", {k: v for k, v in resume.items() if k != 'erreurs'})
    return resume


# ------------------------------------------------------------------
# Synchronisation de sa propre fiche à la connexion
# ------------------------------------------------------------------
def synchroniser_employe(employe, jeton_utilisateur=None):
    if not employe.code_barre:
        return []
    code = employe.code_barre.strip().upper()
    donnees = lire_employes_externes(jeton_utilisateur)
    emp_data = next((e for e in donnees if str(e.get('codeBarre', '')).strip().upper() == code), None)
    if emp_data is None:
        logger.warning("Synchro connexion : matricule %s introuvable dans l'API RH", code)
        return []
    return appliquer_donnees(employe, emp_data)


DELAI_NOUVEL_ESSAI = 300   # en cas d'échec, on réessaie à la prochaine ouverture après 5 minutes


def _cle_synchro(employe_id):
    return f'sync_connexion_{employe_id}'


def _executer(employe_id, jeton):
    close_old_connections()
    try:
        employe = Employe.objects.filter(pk=employe_id).first()
        if employe:
            modifies = synchroniser_employe(employe, jeton)
            logger.info("Synchro connexion %s : %s", employe.code_barre,
                        ', '.join(modifies) if modifies else 'déjà à jour')
    except ApiRhIndisponible as exc:
        logger.warning("Synchro connexion reportée : %s", exc)
        cache.set(_cle_synchro(employe_id), True, DELAI_NOUVEL_ESSAI)
    except Exception:
        logger.exception("Synchro connexion impossible (employé %s)", employe_id)
        cache.set(_cle_synchro(employe_id), True, DELAI_NOUVEL_ESSAI)
    finally:
        close_old_connections()


def declencher_a_la_connexion(request, employe):
    """
    Met à jour la fiche de la personne qui ouvre l'application, en arrière-plan (sans la ralentir).
    SYNC_CONNEXION_INTERVALLE_HEURES : 0 = à chaque ouverture ; N = au plus une fois toutes les N heures.
    """
    if not employe or not settings.EXTERNAL_API_EMPLOYE_URL:
        return False
    intervalle = int(settings.SYNC_CONNEXION_INTERVALLE_HEURES * 3600)
    if intervalle > 0 and not cache.add(_cle_synchro(employe.pk), True, intervalle):
        return False
    entete = request.headers.get('Authorization', '')
    jeton = entete.split(' ', 1)[1] if entete.startswith('Bearer ') else None
    threading.Thread(target=_executer, args=(employe.pk, jeton), daemon=True).start()
    return True
