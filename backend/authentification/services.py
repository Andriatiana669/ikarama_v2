# backend/authentification/services.py
"""
Vérification des jetons et rattachement à un compte Django + une fiche Employé.

Seuls les jetons Keycloak sont acceptés : chaque jeton est validé par Keycloak
lui-même (endpoint userinfo), puis gardé quelques secondes en cache.
Aucune clé n'est à configurer : il suffit de KEYCLOAK_SERVER_URL et KEYCLOAK_REALM.
"""
import hashlib
import logging
import time

import jwt
import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError, transaction
from rest_framework.exceptions import AuthenticationFailed

from ikarama.reseau import decrire_erreur_reseau
from utilisateurs.models import Employe

logger = logging.getLogger(__name__)


def _cle_cache(jeton):
    return 'jeton_' + hashlib.sha256(jeton.encode()).hexdigest()


def _revendications_non_verifiees(jeton):
    """Lecture SANS vérification : sert uniquement à savoir qui a émis le jeton."""
    try:
        return jwt.decode(jeton, options={'verify_signature': False})
    except jwt.InvalidTokenError as exc:
        raise AuthenticationFailed('Jeton illisible.') from exc


def _identite_keycloak(jeton, revendications):
    url = settings.KEYCLOAK.get('USERINFO_URL')
    if not url:
        raise AuthenticationFailed('Keycloak non configuré sur le serveur.')

    cle = _cle_cache(jeton)
    identite = cache.get(cle)
    if identite:
        return identite

    try:
        reponse = requests.get(url, headers={'Authorization': f'Bearer {jeton}'},
                               verify=settings.CA_BUNDLE, timeout=5)
    except requests.RequestException as exc:
        logger.error("Keycloak injoignable (%s) : %s", url, decrire_erreur_reseau(exc))
        raise AuthenticationFailed("Service d'authentification injoignable.") from exc
    if reponse.status_code != 200:
        raise AuthenticationFailed('Jeton expiré ou invalide.')

    infos = reponse.json()
    identite = {
        'username': infos.get('preferred_username', ''),
        'email': infos.get('email', ''),
        'prenom': infos.get('given_name', ''),
        'nom': infos.get('family_name', ''),
        'keycloak_id': infos.get('sub', ''),
    }
    # Cache court, jamais au-delà de l'expiration du jeton
    restant = int(revendications.get('exp', 0) - time.time())
    duree = min(settings.DUREE_CACHE_JETON, restant)
    if duree > 0:
        cache.set(cle, identite, duree)
    return identite


def identite_depuis_jeton(jeton):
    """Valide le jeton et renvoie {username, email, prenom, nom, keycloak_id}."""
    revendications = _revendications_non_verifiees(jeton)
    if '/realms/' not in str(revendications.get('iss', '')):
        raise AuthenticationFailed("Jeton non reconnu : seuls les jetons Keycloak sont acceptés.")
    return _identite_keycloak(jeton, revendications)


def utilisateur_depuis_identite(identite):
    """
    Retrouve (ou crée) le compte Django et la fiche Employé correspondant au matricule.
    Les comptes créés n'ont pas de mot de passe : la connexion passe toujours par le jeton.
    """
    username = (identite.get('username') or '').strip().upper()
    if not username:
        raise AuthenticationFailed('Le jeton ne contient pas de matricule.')

    employe = Employe.objects.select_related('user').filter(code_barre__iexact=username).first()
    user = employe.user if employe and employe.user else User.objects.filter(username__iexact=username).first()

    if user is None:
        try:
            with transaction.atomic():
                user = User(username=username, email=identite.get('email', ''),
                            first_name=identite.get('prenom', ''), last_name=identite.get('nom', ''))
                user.set_unusable_password()
                user.save()
        except IntegrityError:   # deux premières requêtes simultanées
            user = User.objects.get(username__iexact=username)

    if not user.is_active:
        raise AuthenticationFailed('Ce compte est désactivé.')

    if employe is None:
        employe = Employe.objects.filter(user=user).first()
    if employe is None:
        try:
            with transaction.atomic():
                Employe.objects.create(
                    code_barre=username,
                    nom=identite.get('nom') or 'À synchroniser',
                    prenom=identite.get('prenom') or 'À synchroniser',
                    email=identite.get('email') or None,
                    keycloak_id=identite.get('keycloak_id') or None,
                    user=user,
                )
        except IntegrityError:
            pass
    elif employe.user_id is None or (identite.get('keycloak_id') and not employe.keycloak_id):
        employe.user = user
        employe.keycloak_id = employe.keycloak_id or identite.get('keycloak_id') or None
        employe.save(update_fields=['user', 'keycloak_id'])

    return user
