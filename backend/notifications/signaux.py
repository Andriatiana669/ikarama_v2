# backend/notifications/signaux.py
"""Notifications automatiques : ajout comme responsable ou membre d'une affaire."""
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from marches.models import Affaire

from .services import notifier


def _ajout(role):
    def recepteur(sender, instance, action, pk_set, **kwargs):
        if action != 'post_add' or not pk_set or not isinstance(instance, Affaire):
            return
        nom = f'{instance.num_affaire} - {instance.nom}' if instance.num_affaire else instance.nom
        notifier(pk_set, 'affaire', f'Vous êtes maintenant {role} de l’affaire « {nom} »',
                 lien='/marches/mes-marches', cle=f'affaire-{instance.pk}-{role}')
    return recepteur


m2m_changed.connect(_ajout('responsable'), sender=Affaire.responsables.through, weak=False)
m2m_changed.connect(_ajout('membre'), sender=Affaire.membres.through, weak=False)
