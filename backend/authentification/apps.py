# backend/authentification/apps.py
from django.apps import AppConfig
from django.db.models.signals import post_migrate


def creer_table_cache(sender, **kwargs):
    """
    Crée la table du cache (settings.CACHES) à chaque `migrate`, si elle n'existe pas.
    Évite d'avoir à lancer `python manage.py createcachetable` à la main.
    """
    from django.core.management import call_command
    call_command('createcachetable', verbosity=0)


class AuthentificationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'authentification'
    verbose_name = 'Authentification'

    def ready(self):
        post_migrate.connect(creer_table_cache, sender=self)
