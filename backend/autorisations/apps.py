# backend/autorisations/apps.py
from django.apps import AppConfig


class AutorisationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'autorisations'
    verbose_name = 'Autorisations'

    def ready(self):
        from . import signals  # noqa: F401  (branche les signaux)
