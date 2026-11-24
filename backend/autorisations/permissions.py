# backend/autorisations/permissions.py
"""
Point d'entrée UNIQUE des contrôles d'accès de l'API.

Aujourd'hui : il faut simplement être connecté (les administrateurs Django
ont tous les droits). Plus tard, le système de « skins » sera branché ici,
dans `a_le_droit()`, sans avoir à modifier chaque vue.

Utilisation dans une vue :

    class MaVue(viewsets.ModelViewSet):
        module = 'equipes'          # nom du module pour les futurs skins
        # permission_classes : rien à préciser, AccesModule est la valeur par défaut

Les actions d'une vue sont traduites en verbe :
    list / retrieve      -> 'voir'
    create               -> 'creer'
    update / partial_... -> 'modifier'
    destroy              -> 'supprimer'
    action personnalisée -> attribut `verbe` de la vue, ou 'modifier' par défaut
"""
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission

from .acces import a_acces

VERBES_PAR_ACTION = {
    'list': 'voir',
    'retrieve': 'voir',
    'create': 'creer',
    'update': 'modifier',
    'partial_update': 'modifier',
    'destroy': 'supprimer',
}


def est_administrateur(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.is_staff))


def a_le_droit(user, verbe, module, cible=None):
    """
    Règle centrale, appelée pour chaque requête (AccesModule).
    Modules de Paramètres > Autorisation (voir droits.MODULES) : moteur de décision des rôles.
    Autres modules : il suffit d'être connecté (les règles métier des vues s'appliquent).
    Le périmètre (sur quelles personnes / affaires) est contrôlé par les vues avec droits.q_droit / peut_sur.
    """
    if not (user and user.is_authenticated):
        return False
    if est_administrateur(user):
        return True
    from .droits import MODULES, peut
    if module in MODULES:
        return peut(user, module, verbe)
    return True


class AccesSiteRefuse(PermissionDenied):
    """La personne ne respecte pas les règles d'accès au site (le frontend affiche la page dédiée)."""
    default_detail = "Vous n'avez pas accès à Ikarama."
    default_code = 'acces_refuse'


def verifier_acces_site(user):
    """Lève AccesSiteRefuse si la personne n'a pas accès au site (superadmins compris)."""
    if not a_acces(getattr(user, 'employe', None)):
        raise AccesSiteRefuse()


def verbe_de_la_requete(request, view):
    action = getattr(view, 'action', None)
    verbes = getattr(view, 'verbes_actions', {})
    if action in verbes:            # la vue peut préciser (ex. DELETE d'une affaire = archiver)
        return verbes[action]
    if action in VERBES_PAR_ACTION:
        return VERBES_PAR_ACTION[action]
    if action:
        return 'voir' if request.method in SAFE_METHODS else 'modifier'
    return 'voir' if request.method in SAFE_METHODS else 'modifier'


class DroitManquant(PermissionDenied):
    default_code = 'droit_manquant'


class AccesModule(BasePermission):
    """Permission par défaut de toute l'API (voir REST_FRAMEWORK dans settings.py)."""
    message = "Vous n'avez pas l'autorisation d'effectuer cette action."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        # 1. Accès au site (règles de Paramètres > Accès au site)
        if getattr(view, 'controle_acces_site', True):
            verifier_acces_site(request.user)
        # 2. Droits par module (Paramètres > Autorisation)
        module = getattr(view, 'module', None)
        verbe = verbe_de_la_requete(request, view)
        if not a_le_droit(request.user, verbe, module):
            from .droits import ACTIONS, MODULES
            if module in MODULES:
                raise DroitManquant(f"Vous n’avez pas le droit « {ACTIONS.get(verbe, verbe)} » sur {MODULES[module]['libelle']}.")
            return False
        return True

    def has_object_permission(self, request, view, obj):
        return True   # le périmètre est appliqué par les vues (droits.q_droit / peut_sur)


class AdministrateurUniquement(BasePermission):
    """Réservé aux comptes Django staff / superuser QUI ont accès au site."""
    message = "Action réservée aux administrateurs."

    def has_permission(self, request, view):
        if not est_administrateur(request.user):
            return False
        verifier_acces_site(request.user)
        return True
