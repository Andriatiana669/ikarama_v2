# backend/pointages/urls.py
from rest_framework.routers import SimpleRouter

from .everwin import EverwinViewSet
from .suivi import SuiviPointageViewSet, VerificationViewSet
from .views import PointageViewSet

router = SimpleRouter()
# « tous » et « verification » avant les pointages personnels (sinon pris pour un identifiant)
router.register('tous', SuiviPointageViewSet, basename='pointage-suivi')
router.register('verification', VerificationViewSet, basename='pointage-verification')
router.register('everwin', EverwinViewSet, basename='pointage-everwin')
router.register('', PointageViewSet, basename='pointage')

urlpatterns = router.urls
