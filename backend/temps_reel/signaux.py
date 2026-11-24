# backend/temps_reel/signaux.py
"""Diffuse les changements : ligne de feuille, notification, planning (planification et pointages)."""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from gsheets.models import LigneFeuille
from notifications.models import Notification
from planning.models import AffectationPlanning
from pointages.models import Pointage

from .diffusion import feuille_modifiee, nouvelle_notification, planning_modifie


@receiver(post_save, sender=LigneFeuille)
def ligne_enregistree(sender, instance, **kwargs):
    feuille_modifiee(instance.feuille_id)
    planning_modifie()   # statut « En train de faire » d'une ligne


@receiver([post_save, post_delete], sender=AffectationPlanning)
@receiver([post_save, post_delete], sender=Pointage)
def planning_change(sender, instance, **kwargs):
    planning_modifie()


@receiver(post_save, sender=Notification)
def notification_creee(sender, instance, created, **kwargs):
    if created:
        nouvelle_notification(instance.destinataire_id)
