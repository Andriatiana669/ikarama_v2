# backend/rendements/models.py
"""
Paramètres > Rendement & Note : réglages des formules des feuilles (communs à toutes les feuilles).

  Rendement prod   = Quantité ÷ Temps de prod × heures_par_jour
  Rendement total  = Quantité ÷ (Temps de prod + Temps de contrôle + Temps de reprise) × heures_par_jour
  Note de rendement = note_objectif × (Rendement total ÷ Rendement objectif), plafonnée à note_max
  Note de qualité :
    - feuille avec critères : moyenne des critères remplis (chacun entre note_critere_min et note_critere_max)
    - feuille sans critère   : pourcentage = Temps de reprise ÷ Temps de prod × 100, puis note de la tranche
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

TRANCHES_PAR_DEFAUT = [
    {'jusqua': 15, 'note': 5},     # moins de 15 %          -> 5
    {'jusqua': 35, 'note': 4},     # de 15 % à moins de 35 % -> 4
    {'jusqua': 55, 'note': 3},
    {'jusqua': 85, 'note': 2},
    {'jusqua': None, 'note': 1},   # 85 % et plus            -> 1
]


def tranches_par_defaut():
    return [dict(t) for t in TRANCHES_PAR_DEFAUT]


class ParametresRendement(models.Model):
    """Une seule ligne (id = 1) : utiliser ParametresRendement.actuels()."""
    heures_par_jour = models.DecimalField('heures par jour', max_digits=5, decimal_places=2, default=Decimal('8'))
    note_objectif = models.DecimalField("note quand l'objectif est atteint", max_digits=4, decimal_places=2,
                                        default=Decimal('2.5'))
    note_max = models.DecimalField('note maximale', max_digits=4, decimal_places=2, default=Decimal('5'))
    note_critere_min = models.DecimalField('note minimale d’un critère', max_digits=4, decimal_places=2, default=Decimal('1'))
    note_critere_max = models.DecimalField('note maximale d’un critère', max_digits=4, decimal_places=2, default=Decimal('5'))
    tranches_reprise = models.JSONField(
        'tranches de la note de qualité (sans critère)', default=tranches_par_defaut,
        help_text='Liste ordonnée {"jusqua": pourcentage ou null pour la dernière, "note": nombre}',
    )
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Paramètres Rendement & Note'
        verbose_name_plural = 'Paramètres Rendement & Note'

    def __str__(self):
        return 'Paramètres Rendement & Note'

    @classmethod
    def actuels(cls):
        objet, _ = cls.objects.get_or_create(pk=1)
        return objet

    def clean(self):
        if self.heures_par_jour <= 0:
            raise ValidationError({'heures_par_jour': 'Doit être supérieur à 0.'})
        if self.note_objectif <= 0 or self.note_objectif > self.note_max:
            raise ValidationError({'note_objectif': 'Doit être entre 0 et la note maximale.'})
        if self.note_critere_min >= self.note_critere_max:
            raise ValidationError({'note_critere_max': 'Doit être supérieure à la note minimale.'})
        tranches = self.tranches_reprise
        if not isinstance(tranches, list) or not tranches:
            raise ValidationError({'tranches_reprise': 'Indiquez au moins une tranche.'})
        precedent = -1
        for index, t in enumerate(tranches):
            derniere = index == len(tranches) - 1
            jusqua, note = t.get('jusqua'), t.get('note')
            if note is None or float(note) < 0:
                raise ValidationError({'tranches_reprise': f'Tranche {index + 1} : note manquante.'})
            if derniere:
                if jusqua is not None:
                    raise ValidationError({'tranches_reprise': 'La dernière tranche n’a pas de limite (« et plus »).'})
            elif jusqua is None or float(jusqua) <= precedent:
                raise ValidationError({'tranches_reprise': 'Les limites doivent être croissantes.'})
            else:
                precedent = float(jusqua)

    def save(self, *args, **kwargs):
        self.pk = 1
        self.full_clean()
        super().save(*args, **kwargs)


class ParametresGraphiques(models.Model):
    """
    Paramètres > Graphiques : réglages des graphiques du Rendement, en un seul endroit (une seule ligne, pk=1).

      Globale   : tâches du camembert « Somme du temps par tâche » (aucune = toutes).
      Evolution : deux courbes superposées, chacune = un groupe de tâches (nom, couleur, tâches).
      Réel vs Objectif : barre 1 = le réel (ses tâches), barre 2 = le Rendement objectif (nom, couleur).
      Analyse : seuils des zones (beaucoup / peu de temps) et des badges (aide, adaptation, baisse soudaine).
    """
    taches_camembert = models.ManyToManyField('marches.Tache', blank=True, related_name='+',
                                              verbose_name='tâches du camembert (Globale)')
    courbe1_nom = models.CharField('nom de la courbe 1', max_length=60, default='Courbe 1')
    courbe1_couleur = models.CharField('couleur de la courbe 1', max_length=7, default='#24497A')
    courbe1_taches = models.ManyToManyField('marches.Tache', blank=True, related_name='+', verbose_name='tâches de la courbe 1')
    courbe2_nom = models.CharField('nom de la courbe 2', max_length=60, default='Courbe 2')
    courbe2_couleur = models.CharField('couleur de la courbe 2', max_length=7, default='#E94242')
    courbe2_taches = models.ManyToManyField('marches.Tache', blank=True, related_name='+', verbose_name='tâches de la courbe 2')
    # Réel vs Objectif : deux barres par employé, chacune = un groupe de tâches
    barre1_nom = models.CharField('nom de la barre 1', max_length=60, default='Barre 1')
    barre1_couleur = models.CharField('couleur de la barre 1', max_length=7, default='#24497A')
    barre1_taches = models.ManyToManyField('marches.Tache', blank=True, related_name='+', verbose_name='tâches de la barre 1')
    barre2_nom = models.CharField('nom de la barre 2', max_length=60, default='Barre 2')
    barre2_couleur = models.CharField('couleur de la barre 2', max_length=7, default='#B7791F')
    barre2_taches = models.ManyToManyField('marches.Tache', blank=True, related_name='+', verbose_name='tâches de la barre 2')
    # Autorise le mode « Données des feuilles » dans les onglets du Rendement (anciennes données sans pointage)
    donnees_feuilles = models.BooleanField('autoriser les données des feuilles', default=False)
    # Autorise le mode « Données des pointages » (affaires pointées sans feuille)
    donnees_pointages = models.BooleanField('autoriser les données des pointages', default=False)
    # Synchronisation des données : mêmes Affaires et Prestations dans les onglets du Rendement (pour tout le monde)
    synchronisation = models.BooleanField('synchroniser les affaires et prestations entre les onglets', default=False)
    # Analyse : seuils des zones et des badges automatiques
    analyse_seuil_temps = models.PositiveSmallIntegerField('« beaucoup de temps » à partir de (%)', default=40)
    analyse_seuil_aide = models.PositiveSmallIntegerField('aide à partir de (% du temps hors de ses lignes)', default=50)
    analyse_mois_adaptation = models.PositiveSmallIntegerField("mois d'adaptation", default=2)
    analyse_seuil_baisse = models.PositiveSmallIntegerField('baisse soudaine à partir de (%)', default=30)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Paramètres des graphiques'
        verbose_name_plural = 'Paramètres des graphiques'

    @classmethod
    def actuels(cls):
        objet, _ = cls.objects.get_or_create(pk=1)
        return objet
