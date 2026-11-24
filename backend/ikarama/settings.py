# backend/ikarama/settings.py
"""
Configuration Django du projet Ikarama.

Toutes les valeurs propres à un environnement (secrets, URL, base de données)
sont lues dans le fichier `.env` situé à la RACINE du dépôt (à côté de backend/
et frontend/). Voir `.env.example`.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent          # .../backend
RACINE_PROJET = BASE_DIR.parent                             # .../ (racine du dépôt)
load_dotenv(RACINE_PROJET / '.env')


def env_bool(nom, defaut=False):
    """Lit une variable booléenne : 'true', '1', 'oui', 'yes' (insensible à la casse)."""
    valeur = os.getenv(nom)
    if valeur is None or valeur.strip() == '':
        return defaut
    return valeur.strip().lower() in ('true', '1', 'oui', 'yes')


def env_liste(nom, defaut=''):
    """Lit une liste séparée par des virgules, sans éléments vides."""
    return [v.strip() for v in os.getenv(nom, defaut).split(',') if v.strip()]


# ------------------------------------------------------------------
# Sécurité
# ------------------------------------------------------------------
SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = env_bool('DEBUG', False)

if not SECRET_KEY:
    if DEBUG:
        # Clé jetable, uniquement pour le développement local
        from django.core.management.utils import get_random_secret_key
        SECRET_KEY = get_random_secret_key()
    else:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured("SECRET_KEY doit être défini dans le fichier .env")

ALLOWED_HOSTS = env_liste('ALLOWED_HOSTS', 'localhost,127.0.0.1')
CORS_ALLOWED_ORIGINS = env_liste('CORS_ALLOWED_ORIGINS', 'http://localhost:4002')
CSRF_TRUSTED_ORIGINS = env_liste('CSRF_TRUSTED_ORIGINS')
CORS_ALLOW_CREDENTIALS = True

if DEBUG:
    # En développement : le frontend lancé sur localhost / 127.0.0.1 (n'importe quel port) est accepté
    CORS_ALLOWED_ORIGIN_REGEXES = [r'^http://(localhost|127\.0\.0\.1)(:\d+)?$']

# ------------------------------------------------------------------
# Applications
# ------------------------------------------------------------------
INSTALLED_APPS = [
    'daphne',            # serveur ASGI (WebSocket) ; doit précéder django.contrib.staticfiles
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Bibliothèques
    'rest_framework',
    'corsheaders',

    # Socle (repris d'Alimanaka)
    'authentification',
    'utilisateurs',
    'equipes',
    'autorisations',

    # Métier Ikarama (à développer)
    'pointages',
    'gsheets',
    'marches',
    'rendements',
    'notifications',
    'planning',
    'channels',
    'temps_reel',
    'affichage_ev',
    'profils',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ikarama.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ikarama.wsgi.application'

# ------------------------------------------------------------------
# Base de données
# PostgreSQL par défaut. DB_ENGINE=sqlite uniquement pour un essai local rapide.
# ------------------------------------------------------------------
if os.getenv('DB_ENGINE', 'postgresql').lower() == 'sqlite':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'ikarama'),
            'USER': os.getenv('DB_USER', ''),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ------------------------------------------------------------------
# Langue et fuseau horaire (mêmes choix qu'Alimanaka)
# ------------------------------------------------------------------
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = os.getenv('TIME_ZONE', 'Indian/Antananarivo')
USE_I18N = True
USE_TZ = False

# ------------------------------------------------------------------
# Fichiers statiques et uploadés
# ------------------------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_ROOT.mkdir(exist_ok=True)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

# ------------------------------------------------------------------
# Django REST Framework
# ------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'authentification.authentication.JetonAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'autorisations.permissions.AccesModule',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'ikarama.pagination.PaginationStandard',
    'PAGE_SIZE': 25,
    'EXCEPTION_HANDLER': 'ikarama.gestion_erreurs.gestionnaire_erreurs',
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
}

# ------------------------------------------------------------------
# Authentification
# ------------------------------------------------------------------
# Certificats pour les appels HTTPS (Keycloak, API RH) :
#   CA_BUNDLE=                      -> certificats publics fournis avec Python (certifi)
#   CA_BUNDLE=systeme               -> certificats reconnus par Windows / Linux (comme le navigateur)
#   CA_BUNDLE=D:/certs/ca.pem       -> fichier .pem de l'autorité interne
#   CA_BUNDLE=desactive             -> AUCUNE vérification (comme Alimanaka). Accepté aussi avec DEBUG=False :
#                                      la gestion du certificat revient à l'équipe de déploiement. Un avertissement
#                                      s'affiche à chaque démarrage et dans Paramètres > Contrôles de cohérence.
_ca = os.getenv('CA_BUNDLE', '').strip()
if _ca.lower() == 'desactive':
    import sys
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    print("ATTENTION : vérification des certificats HTTPS DÉSACTIVÉE (CA_BUNDLE=desactive) pour Keycloak et l'API RH. "
          "Une machine du réseau pourrait se faire passer pour eux : renseigner CA_BUNDLE=systeme ou le chemin du "
          "certificat .pem dès que possible.", file=sys.stderr)
    CA_BUNDLE = False
elif _ca.lower() == 'systeme':
    import truststore
    truststore.inject_into_ssl()
    CA_BUNDLE = True
else:
    CA_BUNDLE = _ca or True

KEYCLOAK = {
    'SERVER_URL': os.getenv('KEYCLOAK_SERVER_URL', '').rstrip('/'),
    'REALM': os.getenv('KEYCLOAK_REALM', ''),
    'CLIENT_ID': os.getenv('KEYCLOAK_CLIENT_ID', ''),
}
KEYCLOAK['USERINFO_URL'] = (
    f"{KEYCLOAK['SERVER_URL']}/realms/{KEYCLOAK['REALM']}/protocol/openid-connect/userinfo"
    if KEYCLOAK['SERVER_URL'] and KEYCLOAK['REALM'] else ''
)

# Durée pendant laquelle un jeton validé par Keycloak est gardé en cache (secondes)
DUREE_CACHE_JETON = int(os.getenv('DUREE_CACHE_JETON', '60'))

# ------------------------------------------------------------------
# API RH externe (synchronisation des employés)
# ------------------------------------------------------------------
EXTERNAL_API_EMPLOYE_URL = os.getenv('EXTERNAL_API_EMPLOYE_URL', '')
EXTERNAL_API_KEYCLOAK = {
    'SERVER_URL': os.getenv('EXTERNAL_API_KEYCLOAK_SERVER_URL', '').rstrip('/'),
    'REALM': os.getenv('EXTERNAL_API_KEYCLOAK_REALM', ''),
    'CLIENT_ID': os.getenv('EXTERNAL_API_KEYCLOAK_CLIENT_ID', ''),
    'CLIENT_SECRET': os.getenv('EXTERNAL_API_KEYCLOAK_CLIENT_SECRET', ''),
}
# Une synchronisation automatique par personne au plus toutes les N heures
# Durée (s) pendant laquelle la liste de l'API RH est réutilisée. 0 = toujours relire l'API RH
DUREE_CACHE_API_RH = int(os.getenv('DUREE_CACHE_API_RH', '60'))
# 0 = mise à jour de sa fiche à chaque ouverture de l'application ; N = au plus toutes les N heures
SYNC_CONNEXION_INTERVALLE_HEURES = float(os.getenv('SYNC_CONNEXION_INTERVALLE_HEURES', '0'))

# ------------------------------------------------------------------
# Cache (partagé entre les workers via la base de données)
# La table est créée automatiquement à chaque `migrate` (authentification/apps.py)
# ------------------------------------------------------------------
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'ikarama_cache',
    }
}

# ------------------------------------------------------------------
# Sécurité HTTPS (activer en production derrière HTTPS)
# ------------------------------------------------------------------
if env_bool('HTTPS', False):
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ------------------------------------------------------------------
# Journalisation (avec rotation : 5 fichiers de 5 Mo)
# ------------------------------------------------------------------
DOSSIER_LOGS = BASE_DIR / 'logs'
DOSSIER_LOGS.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {'format': '{levelname} {asctime} {name} {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'standard'},
        'fichier': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': DOSSIER_LOGS / 'ikarama.log',
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'encoding': 'utf-8',
            'formatter': 'standard',
        },
    },
    'root': {'handlers': ['console', 'fichier'], 'level': 'INFO'},
    'loggers': {
        'django': {'handlers': ['console', 'fichier'], 'level': 'WARNING', 'propagate': False},
    },
}


# ------------------------------------------------------------------
# E-mail (récapitulatif quotidien des notifications)
# Sans EMAIL_HOST, les e-mails sont écrits dans la console (aucun envoi).
# ------------------------------------------------------------------
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND') or (
    'django.core.mail.backends.smtp.EmailBackend' if os.getenv('EMAIL_HOST') else 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)          # lu comme un vrai booléen (« False » n'est pas vrai)
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'Ikarama <ne-pas-repondre@localhost>')
EMAIL_TIMEOUT = 20
# Adresse de l'application dans les e-mails (liens vers les pages)
URL_APPLICATION = os.getenv('URL_APPLICATION', 'http://localhost:4002').rstrip('/')


# ------------------------------------------------------------------
# Temps réel (WebSocket, Django Channels) — voir temps_reel/ et README « Déploiement »
#   REDIS_URL renseigné : file de messages et cache Redis (plusieurs processus serveur possibles).
#   REDIS_URL vide      : mode mémoire, valable pour UN SEUL processus serveur (développement, petite installation).
# ------------------------------------------------------------------
ASGI_APPLICATION = 'ikarama.asgi.application'
REDIS_URL = os.getenv('REDIS_URL', '').strip()
if REDIS_URL:
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels_redis.core.RedisChannelLayer', 'CONFIG': {'hosts': [REDIS_URL]}}}
    # Le même Redis sert de cache partagé (présences dans les feuilles, entre tous les processus)
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': REDIS_URL}}
else:
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}
