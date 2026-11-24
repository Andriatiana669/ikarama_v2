from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import AffectationViewSet, ExportSemaineView, ProjetsPlanifiablesView, SemaineView

router = SimpleRouter()
router.register('affectations', AffectationViewSet, basename='affectation-planning')

urlpatterns = [
    path('semaine/', SemaineView.as_view(), name='planning-semaine'),
    path('semaine/exporter/', ExportSemaineView.as_view(), name='planning-exporter'),
    path('projets/', ProjetsPlanifiablesView.as_view(), name='planning-projets'),
    *router.urls,
]
