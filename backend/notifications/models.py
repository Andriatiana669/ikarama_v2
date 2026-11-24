# backend/notifications/models.py
"""
Notifications : affichées dans l'application (cloche) et résumées par un e-mail quotidien
(commande envoyer_recapitulatif).
"""
from django.db import models

from utilisateurs.models import Employe


class Notification(models.Model):
    TYPES = [
        ('rappel_pointage', 'Rappel de pointage'),
        ('temps_estimatif', 'Temps Estimatif'),
        ('pointage_modifie', 'Pointage modifié par un administrateur'),
        ('import', 'Import'),
        ('affaire', 'Affaire'),
    ]
    destinataire = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=TYPES)
    titre = models.CharField(max_length=200)
    message = models.TextField(blank=True, default='')
    # Page de l'application à ouvrir (ex. /google-sheet/feuilles/3)
    lien = models.CharField(max_length=300, blank=True, default='')
    # Évite d'envoyer deux fois la même alerte non lue (ex. « ligne 12 en rouge »)
    cle = models.CharField(max_length=120, blank=True, default='', db_index=True)
    lu = models.BooleanField(default=False)
    envoyee_par_email = models.BooleanField(default=False)
    cree_le = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-cree_le', '-id']
        indexes = [models.Index(fields=['destinataire', 'lu'], name='notif_destinataire_lu')]

    def __str__(self):
        return f'{self.destinataire} : {self.titre}'
