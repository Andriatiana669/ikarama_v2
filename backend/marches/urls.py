# backend/marches/urls.py
from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views
from .configurations import ConfigurationResponsablesViewSet
from .duree import DureeEstimativeView, ExportDureeEstimativeView

router = SimpleRouter()
router.register('affaires', views.AffaireViewSet, basename='affaire')
router.register('prestations', views.PrestationViewSet, basename='prestation')
router.register('projets', views.ProjetViewSet, basename='projet')
router.register('taches', views.TacheViewSet, basename='tache')
router.register('statuts', views.StatutViewSet, basename='statut')
router.register('descriptions', views.DescriptionViewSet, basename='description')
router.register('configurations-responsables', ConfigurationResponsablesViewSet, basename='configuration-responsables')

urlpatterns = [
    path('duree-estimative/', DureeEstimativeView.as_view(), name='duree-estimative'),
    path('duree-estimative/exporter/', ExportDureeEstimativeView.as_view(), name='duree-estimative-exporter'),
    *router.urls,
]
