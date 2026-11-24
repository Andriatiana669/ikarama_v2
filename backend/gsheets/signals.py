# backend/gsheets/signals.py
# Les feuilles suivent le Marché :
#  - une description ajoutée reçoit sa ligne dans les feuilles concernées ;
#  - une description supprimée emporte ses lignes si elles sont vides, et la suppression
#    est refusée si une ligne contient déjà des données (voir services.py).
#    Cela vaut aussi quand on supprime un Projet / Commune (ses descriptions sont supprimées avec lui).
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from marches.models import Description

from .models import LigneFeuille
from .services import feuilles_concernees, instantane, preparer_suppression_description, synchroniser


@receiver(post_save, sender=Description)
def description_enregistree(sender, instance, created, **kwargs):
    if created:
        for feuille in feuilles_concernees(instance):
            synchroniser(feuille)
    else:
        LigneFeuille.objects.filter(description=instance).update(instantane=instantane(instance))


@receiver(pre_delete, sender=Description)
def description_supprimee(sender, instance, **kwargs):
    preparer_suppression_description(instance)
