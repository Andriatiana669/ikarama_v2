# backend/utilisateurs/urls.py
from rest_framework.routers import SimpleRouter

from .views import EmployeViewSet

router = SimpleRouter()
router.register('', EmployeViewSet, basename='employe')

urlpatterns = router.urls
