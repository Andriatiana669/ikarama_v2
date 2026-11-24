# backend/autorisations/models.py
"""
Règles d'accès au site (Paramètres > Accès au site).

Fonctionnement (voir acces.py) :
  - aucune règle « Autoriser » active  -> tout le monde entre, sauf les personnes « Refusées » ;
  - au moins une règle « Autoriser »   -> seules les personnes concernées entrent ;
  - une règle « Refuser » l'emporte toujours sur une règle « Autoriser ».
Les superadmins sont soumis aux mêmes règles.
"""
from django.core.exceptions import ValidationError
from django.db import models

from utilisateurs.models import Employe


class RegleAcces(models.Model):
    EFFETS = [('AUTORISER', 'Autoriser'), ('REFUSER', 'Refuser')]
    CRITERES = [
        ('POLE', 'Pôle'),
        ('POSTE', 'Poste'),
        ('MATRICULE', 'Matricule (une personne)'),
        ('N1', 'Responsable N+1'),
    ]
    PORTEES = [
        ('DIRECT', 'Ses collaborateurs directs'),
        ('HIERARCHIE', 'Toute la hiérarchie sous lui'),
    ]

    effet = models.CharField(max_length=10, choices=EFFETS, default='AUTORISER')
    critere = models.CharField('critère', max_length=10, choices=CRITERES)
    pole = models.CharField('pôle', max_length=100, blank=True, default='')
    poste = models.CharField(max_length=100, blank=True, default='')
    employe = models.ForeignKey(
        Employe, on_delete=models.CASCADE, null=True, blank=True, related_name='regles_acces',
        verbose_name='employé', help_text='La personne (critère Matricule) ou le responsable (critère N+1)',
    )
    portee = models.CharField('portée', max_length=10, choices=PORTEES, default='DIRECT', blank=True)
    actif = models.BooleanField(default=True)
    commentaire = models.CharField(max_length=255, blank=True, default='')

    cree_par = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='+', verbose_name='créée par')
    created_at = models.DateTimeField('créée le', auto_now_add=True)
    updated_at = models.DateTimeField('modifiée le', auto_now=True)

    class Meta:
        verbose_name = "Règle d'accès au site"
        verbose_name_plural = "Règles d'accès au site"
        ordering = ['-effet', 'critere', 'pole', 'poste', 'id']   # REFUSER avant AUTORISER

    def __str__(self):
        return f"{self.get_effet_display()} : {self.description()}"

    def description(self):
        if self.critere == 'POLE':
            return f"pôle {self.pole}"
        if self.critere == 'POSTE':
            return f"poste {self.poste}"
        nom = self.employe.identifiant if self.employe else '?'
        if self.critere == 'MATRICULE':
            return nom
        return f"{'hiérarchie' if self.portee == 'HIERARCHIE' else 'collaborateurs directs'} de {nom}"

    def clean(self):
        """Seul le champ du critère choisi est gardé ; il doit être rempli."""
        if self.critere == 'POLE':
            if not self.pole:
                raise ValidationError({'pole': 'Choisissez un pôle.'})
            self.poste, self.employe = '', None
        elif self.critere == 'POSTE':
            if not self.poste:
                raise ValidationError({'poste': 'Choisissez un poste.'})
            self.pole, self.employe = '', None
        elif self.critere in ('MATRICULE', 'N1'):
            if not self.employe_id:
                raise ValidationError({'employe': 'Choisissez une personne.'})
            self.pole = self.poste = ''
        if self.critere == 'N1' and self.portee not in ('DIRECT', 'HIERARCHIE'):
            raise ValidationError({'portee': 'Choisissez la portée.'})
        if self.critere != 'N1':
            self.portee = ''

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ======================================================================
# Paramètres > Autorisation : rôles (comme les « skins » d'Alimanaka)
# Un rôle contient des droits (Autoriser / Refuser une action sur un module, avec un périmètre)
# et est attribué à des personnes, des postes ou des pôles. Moteur de décision : autorisations/droits.py.
# ======================================================================
class Role(models.Model):
    nom = models.CharField(max_length=100, unique=True, error_messages={'unique': 'Un rôle porte déjà ce nom.'})
    description = models.TextField(blank=True, default='')
    actif = models.BooleanField(default=True)
    cree_par = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField('créé le', auto_now_add=True)
    updated_at = models.DateTimeField('modifié le', auto_now=True)

    class Meta:
        verbose_name = 'Rôle'
        verbose_name_plural = 'Rôles'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class DroitRole(models.Model):
    """Une ligne de la grille d'un rôle : Autoriser ou Refuser une action d'un module, sur un périmètre."""
    EFFETS = [('AUTORISER', 'Autoriser'), ('REFUSER', 'Refuser')]
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='droits')
    effet = models.CharField(max_length=10, choices=EFFETS, default='AUTORISER')
    module = models.CharField(max_length=30)
    action = models.CharField(max_length=15)
    perimetre = models.CharField('périmètre', max_length=20)
    # Valeur du périmètre selon son type : pôle ou poste (texte), personne, affaire
    valeur = models.CharField(max_length=100, blank=True, default='')
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, null=True, blank=True, related_name='+')
    affaire = models.ForeignKey('marches.Affaire', on_delete=models.CASCADE, null=True, blank=True, related_name='+')

    class Meta:
        verbose_name = 'Droit d’un rôle'
        verbose_name_plural = 'Droits des rôles'
        ordering = ['module', 'action', '-effet', 'id']


class AttributionRole(models.Model):
    """Qui a le rôle : une personne, un poste ou un pôle (attribution automatique)."""
    CRITERES = [('MATRICULE', 'Une personne'), ('POSTE', 'Un poste'), ('POLE', 'Un pôle')]
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='attributions')
    critere = models.CharField('critère', max_length=10, choices=CRITERES)
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, null=True, blank=True, related_name='attributions_roles')
    poste = models.CharField(max_length=100, blank=True, default='')
    pole = models.CharField('pôle', max_length=100, blank=True, default='')
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Attribution d’un rôle'
        verbose_name_plural = 'Attributions des rôles'
        ordering = ['critere', 'pole', 'poste', 'id']

    def description(self):
        if self.critere == 'MATRICULE':
            return self.employe.identifiant if self.employe else '?'
        return f"poste {self.poste}" if self.critere == 'POSTE' else f"pôle {self.pole}"


class JournalAutorisation(models.Model):
    """Qui a changé quels rôles, droits et attributions, et quand."""
    date = models.DateTimeField(auto_now_add=True, db_index=True)
    auteur = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    texte = models.CharField(max_length=500)

    class Meta:
        ordering = ['-date', '-id']
