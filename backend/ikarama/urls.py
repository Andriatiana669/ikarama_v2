# backend/ikarama/urls.py
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from ikarama.accueil import AccueilView
from ikarama.controles import ControlesView
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('authentification.urls')),
    path('api/utilisateurs/', include('utilisateurs.urls')),
    path('api/equipes/', include('equipes.urls')),
    path('api/autorisations/', include('autorisations.urls')),
    path('api/marches/', include('marches.urls')),
    path('api/gsheets/', include('gsheets.urls')),
    path('api/rendements/', include('rendements.urls')),
    path('api/pointages/', include('pointages.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/planning/', include('planning.urls')),
    path('api/controles/', ControlesView.as_view(), name='controles'),
    path('api/accueil/', AccueilView.as_view(), name='accueil'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
