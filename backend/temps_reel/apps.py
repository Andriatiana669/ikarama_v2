from django.apps import AppConfig


class TempsReelConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'temps_reel'
    verbose_name = 'Temps réel'

    def ready(self):
        from . import signaux  # noqa: F401
