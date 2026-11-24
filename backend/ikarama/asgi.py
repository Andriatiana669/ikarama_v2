"""
Point d'entrée ASGI : HTTP (Django) et WebSocket (temps réel, /ws/).
Lancer en production : daphne -b 127.0.0.1 -p 4000 ikarama.asgi:application
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ikarama.settings')
application_http = get_asgi_application()   # initialise Django avant d'importer le reste

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402
from django.urls import path  # noqa: E402

from temps_reel.consumers import TempsReelConsumer  # noqa: E402

application = ProtocolTypeRouter({
    'http': application_http,
    'websocket': AllowedHostsOriginValidator(URLRouter([path('ws/', TempsReelConsumer.as_asgi())])),
})
