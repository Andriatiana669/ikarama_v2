# backend/rendements/urls.py
from django.urls import path

from .views import (AnalyseView, EvolutionView, ExportEvolutionView, ExportGlobaleView, GlobaleView,
                    ParametresGraphiquesView, ReelObjectifView, ExportReelObjectifView, EvaluationView, ExportEvaluationView, AnalyseEmployesView, ExportAnalyseEmployesView, ExportAnalyseView, OptionsAnalyseView, ParametresView, ReinitialiserParametresView)

urlpatterns = [
    path('parametres/', ParametresView.as_view(), name='parametres-rendement'),
    path('parametres/reinitialiser/', ReinitialiserParametresView.as_view(), name='parametres-rendement-reinitialiser'),
    path('analyse/', AnalyseView.as_view(), name='rendement-analyse'),
    path('analyse/options/', OptionsAnalyseView.as_view(), name='rendement-analyse-options'),
    path('analyse/exporter/', ExportAnalyseView.as_view(), name='rendement-analyse-exporter'),
    path('globale/', GlobaleView.as_view(), name='rendement-globale'),
    path('globale/exporter/', ExportGlobaleView.as_view(), name='rendement-globale-exporter'),
    path('evolution/', EvolutionView.as_view(), name='rendement-evolution'),
    path('evolution/exporter/', ExportEvolutionView.as_view(), name='rendement-evolution-exporter'),
    path('graphiques/', ParametresGraphiquesView.as_view(), name='parametres-graphiques'),
    path('reel-objectif/', ReelObjectifView.as_view(), name='rendement-reel-objectif'),
    path('evaluation/', EvaluationView.as_view(), name='rendement-evaluation'),
    path('analyse-employes/', AnalyseEmployesView.as_view(), name='rendement-analyse-employes'),
    path('analyse-employes/exporter/', ExportAnalyseEmployesView.as_view(), name='rendement-analyse-employes-exporter'),
    path('evaluation/exporter/', ExportEvaluationView.as_view(), name='rendement-evaluation-exporter'),
    path('reel-objectif/exporter/', ExportReelObjectifView.as_view(), name='rendement-reel-objectif-exporter'),
]
