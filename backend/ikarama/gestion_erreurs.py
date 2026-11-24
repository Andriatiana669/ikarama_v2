# backend/ikarama/gestion_erreurs.py
"""
Format unique des erreurs de l'API :

    {"detail": "Message lisible", "erreurs": {"champ": ["message", ...]}}

Le frontend (src/api/client.ts) s'appuie sur ce format pour afficher les messages.
"""
import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def _premier_message(erreurs):
    """Renvoie le premier message trouvé dans une structure d'erreurs DRF."""
    if isinstance(erreurs, dict):
        for valeur in erreurs.values():
            message = _premier_message(valeur)
            if message:
                return message
    elif isinstance(erreurs, (list, tuple)):
        for valeur in erreurs:
            message = _premier_message(valeur)
            if message:
                return message
    elif erreurs:
        return str(erreurs)
    return None


def gestionnaire_erreurs(exc, context):
    # Une ValidationError levée dans un modèle (clean/save) devient une erreur 400
    if isinstance(exc, DjangoValidationError):
        exc = ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else exc.messages)

    # Suppression bloquée par une donnée qui l'utilise (on_delete=PROTECT)
    if isinstance(exc, ProtectedError):
        # Message précis quand il a été rédigé pour l'utilisateur (ex. données saisies dans une feuille),
        # sinon on indique ce qui utilise l'élément (« utilisé par : 3 pointages »).
        if type(exc) is not ProtectedError:
            message = exc.args[0]
        else:
            comptes = {}
            for objet in getattr(exc, 'protected_objects', []) or []:
                meta = objet._meta
                comptes.setdefault(meta.label, [0, str(meta.verbose_name).lower(), str(meta.verbose_name_plural).lower()])
                comptes[meta.label][0] += 1
            detail = ', '.join(f'{n} {singulier if n == 1 else pluriel}' for n, singulier, pluriel in comptes.values())
            message = f"Suppression impossible : cet élément est utilisé par : {detail}." if detail \
                else "Suppression impossible : cet élément est utilisé ailleurs."
        return Response({'detail': message, 'code': 'utilise'}, status=status.HTTP_400_BAD_REQUEST)

    reponse = exception_handler(exc, context)

    if reponse is None:
        # Erreur inattendue : détail dans le journal, message générique pour l'utilisateur
        logger.exception("Erreur non gérée sur %s", context.get('request').path if context.get('request') else '?')
        return Response(
            {'detail': "Une erreur interne est survenue. Réessayez ou contactez l'administrateur."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    donnees = reponse.data
    # Code machine de l'erreur (ex. « acces_refuse »), utile au frontend
    code = getattr(exc, 'default_code', None) if not isinstance(exc, ValidationError) else None
    if isinstance(donnees, dict) and set(donnees.keys()) == {'detail'}:
        if code:
            reponse.data = {'detail': donnees['detail'], 'code': getattr(donnees['detail'], 'code', code)}
        return reponse
    reponse.data = {
        'detail': _premier_message(donnees) or 'Requête invalide.',
        'erreurs': donnees,
    }
    return reponse
