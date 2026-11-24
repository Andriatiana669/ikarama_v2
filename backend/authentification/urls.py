# backend/authentification/urls.py
from django.urls import path

from .views import MoiView, SessionAdminView, entree_admin

urlpatterns = [
    path('moi/', MoiView.as_view(), name='auth-moi'),
    path('session-admin/', SessionAdminView.as_view(), name='auth-session-admin'),
    path('entree-admin/', entree_admin, name='auth-entree-admin'),
]
