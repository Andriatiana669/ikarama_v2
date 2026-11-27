# backend/marches/models.py
"""
Marché : configuration des données qui serviront plus tard au Pointage et aux Google Sheets.

  Catalogues communs (saisis une fois) : Prestation (+ ses rendements objectifs), Tâche, Statut.

  Chaîne de travail :
      Affaire ──coche──> Prestations
         └─ pour chaque (Affaire, Prestation) : Projets/Communes
                └─ pour chaque Projet : ses Descriptions (avec quantité)
                   -> la quantité du projet est la somme des quantités de ses descriptions

« Temps » et « Statut » seront calculés plus tard à partir des pointages : aucun champ ici.
"""
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.db.models import Q

from ikarama.modeles import Ordonnable
from utilisateurs.models import Employe


class Horodatage(models.Model):
    cree_par = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='+', verbose_name='créé par')
    cree_le = models.DateTimeField('créé le', auto_now_add=True)
    modifie_le = models.DateTimeField('modifié le', auto_now=True)

    class Meta:
        abstract = True


# ------------------------------------------------------------------
# Catalogues communs
# ------------------------------------------------------------------
class Prestation(Ordonnable, Horodatage):
    nom = models.CharField(max_length=150, unique=True,
                           error_messages={'unique': 'Une prestation porte déjà ce nom.'})
    unite = models.CharField('unité', max_length=50)

    class Meta:
        ordering = ['ordre', 'id']
        verbose_name = 'Prestation'
        verbose_name_plural = 'Prestations'

    def __str__(self):
        return self.nom


class RendementObjectif(Ordonnable):
    """Une des valeurs de « rendement objectif par jour » d'une prestation (Rendement objectif 1, 2, …)."""
    prestation = models.ForeignKey(Prestation, on_delete=models.CASCADE, related_name='rendements')
    valeur = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['ordre', 'id']
        verbose_name = 'Rendement objectif par jour'
        verbose_name_plural = 'Rendements objectifs par jour'
        constraints = [models.UniqueConstraint(fields=['prestation', 'valeur'], name='rendement_unique_par_prestation')]

    def portee_ordre(self):
        return RendementObjectif.objects.filter(prestation_id=self.prestation_id)

    def __str__(self):
        return f"{self.valeur.normalize():f} {self.prestation.unite}/j"


class Tache(Ordonnable, Horodatage):
    """
    Tâche proposée au pointage. Son type relie le temps pointé à une colonne des feuilles :
      PRODUCTION -> Employé + Temps de prod
      CONTROLE   -> Contrôleur + Temps de contrôle
      REPRISE    -> Employé reprise + Temps de reprise
      AUTRE      -> temps pointé, mais rien n'est reporté dans la feuille
    """
    TYPES = [
        ('PRODUCTION', 'Production'),
        ('CONTROLE', 'Contrôle'),
        ('REPRISE', 'Reprise'),
        ('AUTRE', 'Autre'),
    ]
    nom = models.CharField(max_length=150, unique=True,
                           error_messages={'unique': 'Une tâche porte déjà ce nom.'})
    type = models.CharField(max_length=12, choices=TYPES, default='AUTRE')
    # Le pointage peut viser plusieurs descriptions d'un même projet (temps partagé au prorata des quantités)
    plusieurs_descriptions = models.BooleanField('plusieurs descriptions', default=False)
    # Son temps s'ajoute au Temps du Projet / Commune (et donc de la prestation et de l'affaire),
    # sans jamais compter deux fois ce qui est déjà dans les temps des feuilles (voir marches/suivi.py)
    temps_projet = models.BooleanField('ajouter au temps du projet', default=False)

    class Meta:
        ordering = ['ordre', 'id']
        verbose_name = 'Tâche'
        verbose_name_plural = 'Tâches'

    def __str__(self):
        return self.nom


class Statut(Ordonnable, Horodatage):
    """Statut proposé lors du pointage (ex. En cours, Terminé, Bloqué)."""
    nom = models.CharField(max_length=100, unique=True,
                           error_messages={'unique': 'Un statut porte déjà ce nom.'})
    couleur = models.CharField(
        'couleur de fond', max_length=7, default='#E8EEF6',
        validators=[RegexValidator(r'^#[0-9A-Fa-f]{6}$', 'Couleur attendue au format #RRGGBB.')],
    )
    # Un seul statut par défaut : il est donné aux nouvelles lignes des feuilles
    par_defaut = models.BooleanField('par défaut', default=False)
    # Un seul statut prioritaire : ses affaires sont proposées en premier au pointage
    prioritaire_pointage = models.BooleanField('prioritaire au pointage', default=False)
    # La Note de rendement n'apparaît que si toutes les descriptions du projet ont ce statut
    active_note_rendement = models.BooleanField('active la note de rendement', default=False)
    # Donné automatiquement à une ligne dont l'avancement atteint 100 %
    avancement_complet = models.BooleanField('avancement 100 %', default=False)
    # Planning Projet : les lignes de feuille à ce statut disent ce que la personne « est en train de faire »
    en_train_de_faire = models.BooleanField('en train de faire', default=False)
    # Contrôles de cohérence : les descriptions à ce statut ne sont pas signalées « sans quantité » (plusieurs statuts)
    ignorer_sans_quantite = models.BooleanField('ignorer la description sans quantité', default=False)

    # Chacun de ces rôles n'appartient qu'à un seul statut à la fois
    ROLES_UNIQUES = ('par_defaut', 'prioritaire_pointage', 'active_note_rendement', 'avancement_complet', 'en_train_de_faire')

    class Meta:
        ordering = ['ordre', 'id']
        verbose_name = 'Statut'
        verbose_name_plural = 'Statuts'

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        for role in self.ROLES_UNIQUES:
            if getattr(self, role):
                Statut.objects.exclude(pk=self.pk).filter(**{role: True}).update(**{role: False})

    @classmethod
    def defaut(cls):
        return cls.objects.filter(par_defaut=True).first()

    @classmethod
    def prioritaire(cls):
        return cls.objects.filter(prioritaire_pointage=True).first()

    @classmethod
    def pour_note_rendement(cls):
        return cls.objects.filter(active_note_rendement=True).first()

    @classmethod
    def pour_avancement_complet(cls):
        return cls.objects.filter(avancement_complet=True).first()

    @classmethod
    def pour_en_train_de_faire(cls):
        return cls.objects.filter(en_train_de_faire=True).first()


# ------------------------------------------------------------------
# Chaîne Affaire > Prestations > Projets > Descriptions
# ------------------------------------------------------------------
class Affaire(Ordonnable, Horodatage):
    num_affaire = models.CharField("n° d'affaire", max_length=50, blank=True, default='')
    nom = models.CharField("nom de l'affaire", max_length=200)
    # Affaire suivie au pointage seulement (pas de feuille prévue) : les Contrôles de cohérence ne la signalent pas
    pointage_seul = models.BooleanField('pointage seulement (pas de feuille)', default=False)
    # Report DT : Quantité = Quantité linéaire × Surface ÷ Linéaire total (somme des quantités linéaires du projet)
    report_dt = models.BooleanField('report DT', default=False)
    responsables = models.ManyToManyField(Employe, related_name='affaires_responsable')
    membres = models.ManyToManyField(Employe, related_name='affaires_membre')
    prestations = models.ManyToManyField(Prestation, through='AffairePrestation', related_name='affaires')
    actif = models.BooleanField(default=True, help_text='Décoché : affaire archivée')

    class Meta:
        ordering = ['ordre', 'id']
        verbose_name = 'Affaire'
        verbose_name_plural = 'Affaires'
        # Le n° d'affaire est facultatif et peut être partagé par plusieurs affaires

    def __str__(self):
        return f"{self.num_affaire} {self.nom}".strip()

    def raisons_non_supprimable(self):
        """Ce qui empêche la suppression définitive (vide = suppression possible)."""
        raisons = []
        nb_prestations = self.liens_prestations.count()
        nb_projets = self.projets.count()
        nb_descriptions = Description.objects.filter(projet__affaire=self).count()
        if nb_prestations:
            raisons.append(f"{nb_prestations} prestation(s) cochée(s)")
        if nb_projets:
            raisons.append(f"{nb_projets} projet(s) / commune(s)")
        if nb_descriptions:
            raisons.append(f"{nb_descriptions} description(s)")
        return raisons


class AffairePrestation(Ordonnable):
    """Une prestation cochée pour une affaire."""
    affaire = models.ForeignKey(Affaire, on_delete=models.CASCADE, related_name='liens_prestations')
    prestation = models.ForeignKey(Prestation, on_delete=models.PROTECT, related_name='liens_affaires')
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ordre', 'id']
        constraints = [models.UniqueConstraint(fields=['affaire', 'prestation'], name='prestation_unique_par_affaire')]

    def portee_ordre(self):
        return AffairePrestation.objects.filter(affaire_id=self.affaire_id)


class Projet(Ordonnable, Horodatage):
    """Projet / Commune d'une affaire, pour une prestation cochée de cette affaire."""
    affaire = models.ForeignKey(Affaire, on_delete=models.CASCADE, related_name='projets')
    prestation = models.ForeignKey(Prestation, on_delete=models.PROTECT, related_name='projets')
    numero = models.PositiveIntegerField('ID', editable=False,
                                         help_text="Numéro dans l'affaire : 1, 2, 3… (jamais réutilisé)")
    nom = models.CharField('nom du projet / de la commune', max_length=200)
    # Somme des quantités de ses descriptions : calculée automatiquement (voir recalculer_quantite)
    quantite = models.DecimalField('quantité', max_digits=14, decimal_places=2, null=True, blank=True, editable=False)
    rendement = models.ForeignKey(RendementObjectif, on_delete=models.PROTECT, related_name='projets',
                                  verbose_name='rendement objectif par jour')
    date_livraison = models.DateField('date de livraison')

    # Report DT : surface du projet (m²) ; le linéaire total est la somme des quantités linéaires de ses descriptions
    surface_m2 = models.DecimalField('surface (m²)', max_digits=14, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['ordre', 'id']
        verbose_name = 'Projet / Commune'
        verbose_name_plural = 'Projets / Communes'
        constraints = [models.UniqueConstraint(fields=['affaire', 'numero'], name='numero_projet_unique_par_affaire')]

    def portee_ordre(self):
        return Projet.objects.filter(affaire_id=self.affaire_id, prestation_id=self.prestation_id)

    def __str__(self):
        return f"{self.affaire} – {self.numero}. {self.nom}"

    def clean(self):
        if self.affaire_id and self.prestation_id and not AffairePrestation.objects.filter(
                affaire_id=self.affaire_id, prestation_id=self.prestation_id).exists():
            raise ValidationError({'prestation': "Cette prestation n'est pas cochée pour cette affaire."})
        if self.rendement_id and self.prestation_id and self.rendement.prestation_id != self.prestation_id:
            raise ValidationError({'rendement': "Ce rendement objectif n'appartient pas à la prestation."})

    def save(self, *args, **kwargs):
        if self._state.adding and not self.numero:
            dernier = Projet.objects.filter(affaire_id=self.affaire_id).aggregate(m=models.Max('numero'))['m']
            self.numero = (dernier or 0) + 1
        self.full_clean()
        super().save(*args, **kwargs)

    def recalculer_quantite(self):
        """Quantité du projet = somme des quantités de ses descriptions (vide si aucune n'est renseignée)."""
        total = self.descriptions.aggregate(t=models.Sum('quantite'))['t']
        Projet.objects.filter(pk=self.pk).update(quantite=total)
        self.quantite = total


class Description(Ordonnable, Horodatage):
    """Description d'un Projet / Commune, avec sa quantité (temps et statut viendront avec le Pointage)."""
    projet = models.ForeignKey(Projet, on_delete=models.CASCADE, related_name='descriptions')
    numero = models.PositiveIntegerField('ID', editable=False, help_text='Numéro dans le projet : 1, 2, 3… (jamais réutilisé)')
    nom = models.CharField('description', max_length=200)
    quantite = models.DecimalField('quantité', max_digits=14, decimal_places=2, null=True, blank=True)

    # Report DT : quantité linéaire (ML), saisie ; la Quantité en est calculée
    quantite_lineaire = models.DecimalField('quantité linéaire (ML)', max_digits=14, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['ordre', 'id']
        verbose_name = 'Description'
        verbose_name_plural = 'Descriptions'
        constraints = [
            models.UniqueConstraint(fields=['projet', 'numero'], name='numero_description_unique_par_projet'),
            models.UniqueConstraint(fields=['projet', 'nom'], name='description_unique_par_projet',
                                    violation_error_message='Ce projet a déjà une description de ce nom.'),
        ]

    def portee_ordre(self):
        return Description.objects.filter(projet_id=self.projet_id)

    def __str__(self):
        return f"{self.projet} – {self.nom}"

    def save(self, *args, **kwargs):
        if self._state.adding and not self.numero:
            dernier = Description.objects.filter(projet_id=self.projet_id).aggregate(m=models.Max('numero'))['m']
            self.numero = (dernier or 0) + 1
        self.full_clean()
        super().save(*args, **kwargs)
        self.projet.recalculer_quantite()

    def delete(self, *args, **kwargs):
        projet = self.projet
        with transaction.atomic():   # annulé proprement si une feuille refuse la suppression
            resultat = super().delete(*args, **kwargs)
        projet.recalculer_quantite()
        return resultat


class ConfigurationResponsables(models.Model):
    """
    Paramètres > Configurations Responsables : un groupe de personnes nommé, ajouté d'un coup dans le champ
    Responsables d'une affaire. Une seule peut être « par défaut » : elle remplit les Responsables d'une nouvelle affaire.
    """
    nom = models.CharField(max_length=100, unique=True, error_messages={'unique': 'Une configuration porte déjà ce nom.'})
    personnes = models.ManyToManyField(Employe, related_name='configurations_responsables', blank=True)
    par_defaut = models.BooleanField('par défaut', default=False)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuration de responsables'
        verbose_name_plural = 'Configurations de responsables'
        ordering = ['-par_defaut', 'nom']

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.par_defaut:   # une seule configuration par défaut
            ConfigurationResponsables.objects.exclude(pk=self.pk).filter(par_defaut=True).update(par_defaut=False)
