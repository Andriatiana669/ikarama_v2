# backend/utilisateurs/models.py
"""
Fiches employés, alimentées par l'API RH externe.

Le `code_barre` (matricule) est la clé qui relie :
  - le nom d'utilisateur Keycloak,
  - la fiche de l'API RH,
  - le compte Django (User.username).
"""
from django.contrib.auth.models import User
from django.db import models


class Employe(models.Model):
    external_id = models.IntegerField('ID API RH', unique=True, null=True, blank=True)
    code_barre = models.CharField('matricule', max_length=100, unique=True, null=True, blank=True)
    civilite = models.CharField(max_length=20, null=True, blank=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField('prénom', max_length=100)
    prenom_usuel = models.CharField('prénom usuel', max_length=100, null=True, blank=True)
    email = models.EmailField(max_length=254, null=True, blank=True)

    chef = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='subordonnes', verbose_name='responsable direct (N+1)',
    )
    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='employe', verbose_name='compte utilisateur',
    )
    keycloak_id = models.CharField(max_length=255, null=True, blank=True)
    derniere_synchro = models.DateTimeField('dernière synchronisation RH', null=True, blank=True)
    # Première entrée réussie sur le site. Une personne qui s'est déjà connectée reste visible
    # dans l'application même si son accès est retiré ensuite (voir autorisations/acces.py).
    premiere_connexion = models.DateTimeField('première connexion', null=True, blank=True)

    class Meta:
        verbose_name = 'Employé'
        verbose_name_plural = 'Employés'
        ordering = ['nom', 'prenom']

    def __str__(self):
        return f"{self.code_barre or '?'} - {self.nom_affiche}"

    @property
    def nom_affiche(self):
        """Prénom usuel (ou prénom) + nom : le nom à afficher partout."""
        return f"{self.prenom_usuel or self.prenom} {self.nom}".strip()

    @property
    def identifiant(self):
        """« PR00123_Jean » : matricule + prénom usuel (ou prénom s'il n'y a pas de prénom usuel)."""
        prenom = (self.prenom_usuel or self.prenom or '').strip()
        return '_'.join(p for p in (self.code_barre or '', prenom) if p)

    def get_email(self):
        if self.email:
            return self.email
        if self.user and self.user.email:
            return self.user.email
        return None

    def subordonnes_hierarchie(self):
        """Tous les subordonnés (N-1, N-2, ...) sans boucle infinie."""
        resultat, a_traiter, vus = [], [self.pk], {self.pk}
        while a_traiter:
            enfants = list(Employe.objects.filter(chef_id__in=a_traiter).exclude(pk__in=vus))
            a_traiter = []
            for enfant in enfants:
                vus.add(enfant.pk)
                resultat.append(enfant)
                a_traiter.append(enfant.pk)
        return resultat


class EmployePoste(models.Model):
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name='postes')
    pole_id = models.IntegerField('ID pôle (API RH)', null=True, blank=True)
    pole = models.CharField('pôle', max_length=100, null=True, blank=True)
    poste_nom = models.CharField('poste', max_length=100, null=True, blank=True)
    poste_statut = models.CharField('statut', max_length=50, null=True, blank=True)

    class Meta:
        verbose_name = 'Poste employé'
        verbose_name_plural = 'Postes employés'

    def __str__(self):
        return f"{self.employe} - {self.poste_nom}"
