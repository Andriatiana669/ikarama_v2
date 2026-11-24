# backend/autorisations/urls.py
from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import AccesViewSet, RegleAccesViewSet
from .vues_roles import AttributionViewSet, CatalogueView, JournalView, RoleViewSet, TesterAccesView, ValeursView

router = SimpleRouter()
router.register('regles', RegleAccesViewSet, basename='regle-acces')
router.register('acces', AccesViewSet, basename='acces')
router.register('roles', RoleViewSet, basename='role')
router.register('attributions', AttributionViewSet, basename='attribution-role')

urlpatterns = [
    path('catalogue/', CatalogueView.as_view(), name='autorisation-catalogue'),
    path('tester/', TesterAccesView.as_view(), name='autorisation-tester'),
    path('journal/', JournalView.as_view(), name='autorisation-journal'),
    path('valeurs/', ValeursView.as_view(), name='autorisation-valeurs'),
    *router.urls,
]
