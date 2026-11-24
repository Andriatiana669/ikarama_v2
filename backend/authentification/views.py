# backend/authentification/views.py
import secrets

from django.contrib.auth import login
from django.contrib.auth.models import User
from django.core import signing
from django.core.cache import cache
from django.shortcuts import redirect
from django.views.decorators.http import require_GET
from rest_framework.response import Response
from rest_framework.views import APIView

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated

from autorisations.acces import a_acces
from autorisations.droits import droits_de, est_responsable
from autorisations.permissions import AdministrateurUniquement, est_administrateur
from utilisateurs.serializers import EmployeSerializer
from utilisateurs.services_rh import declencher_a_la_connexion


class MoiView(APIView):
    """
    GET /api/auth/moi/
    Appelé par le frontend au démarrage : qui suis-je, ma fiche, mes droits.
    Déclenche aussi la mise à jour de ma fiche depuis l'API RH (en arrière-plan).

    Toujours accessible à une personne connectée, même sans accès au site :
    « acces_site » indique au frontend s'il faut afficher la page « Accès non autorisé ».
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        employe = getattr(user, 'employe', None)
        declencher_a_la_connexion(request, employe)
        acces = a_acces(employe)
        if acces and employe and not employe.premiere_connexion:
            employe.premiere_connexion = timezone.now()
            employe.save(update_fields=['premiere_connexion'])
        if not acces:
            # Le minimum pour la page « Accès non autorisé »
            return Response({
                'id': user.id, 'username': user.username, 'email': user.email,
                'prenom': user.first_name, 'nom': user.last_name,
                'est_administrateur': False, 'acces_site': False,
                'employe': None, 'autorisations': {}, 'est_responsable': False,
            })
        return Response({
            'acces_site': True,
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'prenom': user.first_name,
            'nom': user.last_name,
            'est_administrateur': est_administrateur(user),
            'employe': EmployeSerializer(employe).data if employe else None,
            # Paramètres > Autorisation : {module: [actions permises]} (menu, pages et boutons de l'écran)
            'autorisations': droits_de(user),
            'est_responsable': est_responsable(employe),
        })


# ------------------------------------------------------------------
# Accès automatique à l'administration Django
# ------------------------------------------------------------------
# 1. Le frontend (déjà connecté avec son jeton) demande un TICKET : POST /api/auth/session-admin/
# 2. Il ouvre dans un nouvel onglet : /api/auth/entree-admin/?ticket=...
# 3. Cette page ouvre la session Django puis redirige vers /admin/.
# Le ticket est signé, valable 60 secondes et utilisable une seule fois.
SEL_TICKET = 'ikarama-entree-admin'
DUREE_TICKET = 60


class SessionAdminView(APIView):
    """POST /api/auth/session-admin/ : ticket d'entrée dans l'admin (administrateurs uniquement)."""
    permission_classes = [AdministrateurUniquement]

    def post(self, request):
        nonce = secrets.token_urlsafe(16)
        cache.set(f'ticket_admin_{nonce}', request.user.pk, DUREE_TICKET)
        ticket = signing.dumps({'u': request.user.pk, 'n': nonce}, salt=SEL_TICKET)
        return Response({'url': f'/api/auth/entree-admin/?ticket={ticket}'})


@require_GET
def entree_admin(request):
    """GET /api/auth/entree-admin/?ticket=... : ouvre la session Django et redirige vers /admin/."""
    page_connexion = '/admin/login/?next=/admin/'
    try:
        donnees = signing.loads(request.GET.get('ticket', ''), salt=SEL_TICKET, max_age=DUREE_TICKET)
    except signing.BadSignature:   # ticket absent, modifié ou expiré
        return redirect(page_connexion)

    # Usage unique : le ticket est consommé
    cle = f"ticket_admin_{donnees.get('n')}"
    if cache.get(cle) != donnees.get('u'):
        return redirect(page_connexion)
    cache.delete(cle)

    user = User.objects.filter(pk=donnees['u'], is_active=True).first()
    if not user or not (user.is_staff or user.is_superuser):
        return redirect(page_connexion)
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return redirect('/admin/')
