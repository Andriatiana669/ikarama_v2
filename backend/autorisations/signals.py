# backend/autorisations/signals.py
# Tout changement de règle ou de fiche employé (pôle, poste, N+1) peut changer les accès.
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from utilisateurs.models import Employe, EmployePoste

from .acces import invalider
from .models import RegleAcces


@receiver([post_save, post_delete], sender=RegleAcces)
@receiver([post_save, post_delete], sender=Employe)
@receiver([post_save, post_delete], sender=EmployePoste)
def recalculer_acces(sender, **kwargs):
    invalider()
