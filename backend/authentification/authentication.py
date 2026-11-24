# backend/authentification/authentication.py
"""
Classe d'authentification de toute l'API (déclarée dans settings.REST_FRAMEWORK).
Chaque requête doit porter :  Authorization: Bearer <jeton>
"""
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .services import identite_depuis_jeton, utilisateur_depuis_identite


class JetonAuthentication(BaseAuthentication):

    def authenticate(self, request):
        entete = get_authorization_header(request).split()
        if not entete or entete[0].lower() != b'bearer':
            return None   # pas de jeton : DRF répondra 401 si la vue l'exige
        if len(entete) != 2:
            raise AuthenticationFailed('En-tête Authorization invalide.')

        jeton = entete[1].decode('utf-8', errors='ignore')
        identite = identite_depuis_jeton(jeton)
        return utilisateur_depuis_identite(identite), jeton

    def authenticate_header(self, request):
        # Permet à DRF de répondre 401 (et non 403) quand le jeton manque
        return 'Bearer'
