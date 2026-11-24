# backend/planning/models.py
"""
Planning Projet : ce que l'équipe fait (pointages), ce qu'elle est en train de faire (statut « en cours » des
lignes de feuille) et ce qu'elle fera (affectations planifiées d'un projet / d'une commune à une personne, un jour).
"""
from django.db import models

from marches.models import Projet
from utilisateurs.models import Employe


class AffectationPlanning(models.Model):
    """Un projet / une commune prévu pour une personne, un jour (aujourd'hui ou plus tard)."""
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name='affectations_planning')
    date = models.DateField(db_index=True)
    projet = models.ForeignKey(Projet, on_delete=models.CASCADE, related_name='affectations_planning')
    commentaire = models.CharField(max_length=300, blank=True, default='')
    cree_par = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Affectation du planning'
        verbose_name_plural = 'Affectations du planning'
        ordering = ['date', 'employe_id', 'id']
        constraints = [models.UniqueConstraint(fields=['employe', 'date', 'projet'], name='affectation_unique')]

    def __str__(self):
        return f'{self.employe} — {self.projet} — {self.date:%d/%m/%Y}'
