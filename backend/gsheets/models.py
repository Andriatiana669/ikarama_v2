# backend/gsheets/models.py
"""
Feuilles de suivi (Google Sheet > …) : un tableur dans Ikarama.

  Feuille
    ├─ Périmètre : une ou plusieurs paires (Affaire, Prestation cochée)
    ├─ Critères de CTRL : 1, 2, 3… chacun avec un commentaire
    └─ Lignes : UNE ligne par Description des projets du périmètre (créées et tenues à jour
                automatiquement, voir services.py). Chaque ligne porte la saisie :
                employé, contrôleur, employé reprise, statut, avancement, commentaires,
                nombre de reprises et une note par critère.

Les temps et la date de début viendront du Pointage ; rendements et notes sont calculés
(formules réglables dans Paramètres > Rendement & Note, voir rendements/calculs.py).
"""
from django.core.validators import MaxValueValidator
from django.db import models

from marches.models import Affaire, Description, Horodatage, Prestation, Statut
from utilisateurs.models import Employe


class Feuille(Horodatage):
    nom = models.CharField('nom de la feuille', max_length=200)
    # Avec critères : Note de qualité = moyenne des critères. Sans : d'après le temps de reprise.
    utiliser_criteres = models.BooleanField('utiliser les critères de CTRL', default=True)

    class Meta:
        ordering = ['-cree_le']
        verbose_name = 'Feuille'
        verbose_name_plural = 'Feuilles'

    def __str__(self):
        return self.nom


class PerimetreFeuille(models.Model):
    """Une prestation d'une affaire, incluse dans la feuille."""
    feuille = models.ForeignKey(Feuille, on_delete=models.CASCADE, related_name='perimetres')
    affaire = models.ForeignKey(Affaire, on_delete=models.CASCADE, related_name='perimetres_feuilles')
    prestation = models.ForeignKey(Prestation, on_delete=models.CASCADE, related_name='perimetres_feuilles')

    class Meta:
        ordering = ['affaire__ordre', 'affaire_id', 'prestation__ordre', 'prestation_id']
        constraints = [models.UniqueConstraint(fields=['feuille', 'affaire', 'prestation'], name='perimetre_unique')]


class CritereControle(models.Model):
    feuille = models.ForeignKey(Feuille, on_delete=models.CASCADE, related_name='criteres')
    numero = models.PositiveSmallIntegerField()
    commentaire = models.CharField(max_length=255)

    class Meta:
        ordering = ['numero']
        verbose_name = 'Critère de CTRL'
        verbose_name_plural = 'Critères de CTRL'
        constraints = [models.UniqueConstraint(fields=['feuille', 'numero'], name='critere_numero_unique')]

    def __str__(self):
        return f"Critère {self.numero} : {self.commentaire}"


class LigneFeuille(models.Model):
    feuille = models.ForeignKey(Feuille, on_delete=models.CASCADE, related_name='lignes')
    numero = models.PositiveIntegerField('ID')
    # Si la description est supprimée du Marché, la ligne reste (marquée « retirée ») avec ses saisies
    description = models.ForeignKey(Description, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='lignes_feuilles')
    # Copie des informations du Marché, utilisée seulement quand la description n'existe plus
    instantane = models.JSONField(default=dict, blank=True)

    employe = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    controleur = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    employe_reprise = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    statut = models.ForeignKey(Statut, on_delete=models.SET_NULL, null=True, blank=True, related_name='lignes_feuilles')
    # Statut propre au contrôle : même liste de statuts, valeur à part (n'agit pas sur la note ni le statut du projet)
    statut_controle = models.ForeignKey(Statut, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='lignes_feuilles_controle', verbose_name='statut de contrôle')
    avancement = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)],
                                                  help_text='En pourcentage, de 0 à 100')
    commentaires = models.TextField(blank=True, default='')
    commentaires_controle = models.TextField('commentaires contrôle', blank=True, default='')
    commentaires_reprise = models.TextField('commentaires reprise', blank=True, default='')
    nb_reprises = models.PositiveIntegerField('nombre de reprises', default=0)

    # Rempli plus tard par le Pointage (en heures) : sert aux rendements et aux notes
    date_debut = models.DateField('date de début', null=True, blank=True)
    temps_prod = models.DecimalField('temps de prod (h)', max_digits=8, decimal_places=2, null=True, blank=True)
    temps_controle = models.DecimalField('temps de contrôle (h)', max_digits=8, decimal_places=2, null=True, blank=True)
    temps_reprise = models.DecimalField('temps de reprise (h)', max_digits=8, decimal_places=2, null=True, blank=True)

    modifie_par = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    modifie_le = models.DateTimeField(auto_now=True, db_index=True)   # sert au suivi en direct

    class Meta:
        ordering = ['numero']
        verbose_name = 'Ligne de feuille'
        verbose_name_plural = 'Lignes de feuille'
        constraints = [
            models.UniqueConstraint(fields=['feuille', 'numero'], name='ligne_numero_unique'),
            models.UniqueConstraint(fields=['feuille', 'description'], name='ligne_description_unique'),
        ]

    @property
    def retiree(self):
        return self.description_id is None


class NoteCritere(models.Model):
    ligne = models.ForeignKey(LigneFeuille, on_delete=models.CASCADE, related_name='notes')
    critere = models.ForeignKey(CritereControle, on_delete=models.CASCADE, related_name='notes')
    note = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['ligne', 'critere'], name='note_unique')]


class HistoriqueLigne(models.Model):
    """
    Une modification d'une case : écrite à chaque enregistrement, lue seulement à la demande
    (historique d'une ligne ou de la feuille), pour ne pas ralentir la feuille.
    """
    feuille = models.ForeignKey(Feuille, on_delete=models.CASCADE, related_name='historique')
    ligne = models.ForeignKey(LigneFeuille, on_delete=models.CASCADE, related_name='historique')
    champ = models.CharField(max_length=50)            # code technique (avancement, note_12…)
    libelle = models.CharField(max_length=150)         # libellé lisible (Avancement, Critère 1…)
    ancienne_valeur = models.TextField(blank=True, default='')
    nouvelle_valeur = models.TextField(blank=True, default='')
    auteur = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']
        verbose_name = 'Modification'
        verbose_name_plural = 'Historique des modifications'
        indexes = [
            models.Index(fields=['feuille', '-date'], name='historique_feuille_date'),
            models.Index(fields=['ligne', '-date'], name='historique_ligne_date'),
        ]


class ParametresTempsEstimatif(models.Model):
    """
    Paramètres > Temps Estimatif (une seule ligne, pk=1).

      Temps Estimatif = Quantité ÷ Rendement objectif par jour   (en jours ; × heures par jour pour des heures)
      Ligne en rouge  : Temps de prod ≥ Temps Estimatif
      Ligne en orange : Temps de prod ≥ Temps Estimatif × (100 − marge) %
      Plus de couleur quand la ligne a le statut qui « Active la note de rendement ».
    """
    UNITES = [('heures', 'Heures'), ('jours', 'Jours')]
    unite = models.CharField('unité par défaut', max_length=6, choices=UNITES, default='heures')
    marge = models.PositiveSmallIntegerField('marge avant le rouge (%)', default=20)
    couleur_rouge = models.CharField('couleur « dépassé »', max_length=7, default='#E94242')
    couleur_orange = models.CharField('couleur « proche »', max_length=7, default='#F59E0B')
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Paramètres du temps estimatif'
        verbose_name_plural = 'Paramètres du temps estimatif'

    @classmethod
    def actuels(cls):
        objet, _ = cls.objects.get_or_create(pk=1)
        return objet
