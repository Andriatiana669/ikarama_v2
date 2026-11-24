# backend/gsheets/urls.py
from django.urls import path
from rest_framework.routers import SimpleRouter

from .import_ancien import ImportAncienViewSet
from .views import FeuilleViewSet, HistoriqueViewSet, LigneViewSet, MonResumeView, ParametresTempsEstimatifView, StatutsFeuilleView

router = SimpleRouter()
router.register('feuilles', FeuilleViewSet, basename='feuille')
router.register('lignes', LigneViewSet, basename='ligne')
router.register('historique', HistoriqueViewSet, basename='historique-feuille')
router.register('import-ancien', ImportAncienViewSet, basename='import-ancien')

urlpatterns = [
    path('temps-estimatif/', ParametresTempsEstimatifView.as_view(), name='parametres-temps-estimatif'),
    path('mon-resume/', MonResumeView.as_view(), name='mon-resume'),
    path('statuts/', StatutsFeuilleView.as_view(), name='statuts-feuille'),
    *router.urls,
]
