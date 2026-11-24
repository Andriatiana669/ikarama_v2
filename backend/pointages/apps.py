# backend/pointages/apps.py
from django.apps import AppConfig


class PointagesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pointages'
    verbose_name = 'Pointages'
