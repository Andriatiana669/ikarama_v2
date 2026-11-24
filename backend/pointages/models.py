# backend/pointages/models.py
"""
Pointage : le temps passé par une personne sur une tâche, pour une ligne de feuille
(Affaire > Prestation > Projet > Description).

  H_Durée (minutes_normales) : temps dans la journée de travail 07h30–16h30 des jours ouvrables,
                               moins 1 h si la case « Pause » est cochée.
  HS (minutes_hs)            : temps hors de cette plage, et tout le temps des samedis et dimanches.

Les deux sont calculés automatiquement pour toute la journée (voir calculs.py), puis partagés entre
les descriptions pointées (PartPointage). Pour chaque description présente dans une feuille, sa part
est reportée sur sa ligne selon le type de la tâche (Temps de prod / de contrôle / de reprise).
"""
from django.db import models

from gsheets.models import LigneFeuille
from marches.models import Description, Tache
from utilisateurs.models import Employe


class Pointage(models.Model):
    employe = models.ForeignKey(Employe, on_delete=models.PROTECT, related_name='pointages')
    date = models.DateField(db_index=True)
    heure_debut = models.TimeField('H_Début')
    heure_fin = models.TimeField('H_Fin')
    tache = models.ForeignKey(Tache, on_delete=models.PROTECT, related_name='pointages', verbose_name='tâche')
    commentaire = models.TextField(blank=True, default='')
    # « Pause (−1 h) » : une seule fois par jour, obligatoire les jours ouvrables pointés (voir calculs.py)
    pause = models.BooleanField('pause (−1 h)', default=False)
    # Texte exact ajouté dans la colonne de commentaires des feuilles (retiré si le pointage est supprimé)
    fragment_commentaire = models.TextField(blank=True, default='', editable=False)

    minutes_normales = models.PositiveIntegerField('H_Durée (minutes)', default=0, editable=False)
    minutes_hs = models.PositiveIntegerField('HS (minutes)', default=0, editable=False)

    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date', 'heure_debut', 'id']
        verbose_name = 'Pointage'
        verbose_name_plural = 'Pointages'
        indexes = [models.Index(fields=['employe', 'date'], name='pointage_employe_date')]

    def __str__(self):
        return f"{self.employe} – {self.date} {self.heure_debut:%H:%M}-{self.heure_fin:%H:%M}"


class PartPointage(models.Model):
    """
    Ce qui est pointé : une description du Marché, et la part du temps qui lui revient.
    Un pointage a une seule part (100 %), ou plusieurs si la tâche le permet
    (« Plusieurs descriptions ») : le temps est alors partagé au prorata des quantités.
    """
    pointage = models.ForeignKey(Pointage, on_delete=models.CASCADE, related_name='parts')
    description = models.ForeignKey(Description, on_delete=models.PROTECT, related_name='parts_pointage')
    # Ligne de feuille qui reçoit le temps (vide si la description n'était dans aucune feuille)
    ligne = models.ForeignKey(LigneFeuille, on_delete=models.PROTECT, related_name='parts_pointage', null=True, blank=True)
    part = models.DecimalField(max_digits=7, decimal_places=6, default=1, help_text='Entre 0 et 1, figée au pointage')
    minutes_normales = models.PositiveIntegerField(default=0, editable=False)
    minutes_hs = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ['id']
        verbose_name = 'pointage'
        verbose_name_plural = 'pointages'
        constraints = [models.UniqueConstraint(fields=['pointage', 'description'], name='part_description_unique')]
