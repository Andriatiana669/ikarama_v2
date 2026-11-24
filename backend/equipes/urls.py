# backend/equipes/urls.py
from rest_framework.routers import SimpleRouter

from .views import EquipeViewSet

router = SimpleRouter()
router.register('', EquipeViewSet, basename='equipe')

urlpatterns = router.urls
