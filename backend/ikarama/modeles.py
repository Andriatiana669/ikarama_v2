# backend/ikarama/modeles.py
"""Modèles abstraits communs."""
from django.db import models


class Ordonnable(models.Model):
    """
    Ordre d'affichage modifiable à la souris (poignées ≡). Un nouvel élément se place à la fin.
    Surcharger `portee_ordre()` si l'ordre dépend d'un parent (ex. les projets d'une affaire).
    """
    ordre = models.PositiveIntegerField(default=0, db_index=True, editable=False)

    class Meta:
        abstract = True

    def portee_ordre(self):
        return type(self).objects.all()

    def save(self, *args, **kwargs):
        if self._state.adding and not self.ordre:
            dernier = self.portee_ordre().aggregate(m=models.Max('ordre'))['m']
            self.ordre = (dernier or 0) + 1
        super().save(*args, **kwargs)
