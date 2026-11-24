# backend/marches/suivi.py
"""
Colonnes « Temps » et « Statut » du Marché, calculées en direct depuis les feuilles.

  Description : Temps = Temps de prod + contrôle + reprise de sa ligne de feuille ; Statut = celui de la ligne.
  Projet      : sommes de ses descriptions
                + le temps des tâches « Ajouter au temps du projet » qui n'est pas déjà dans une feuille
                  (tâche Autre, ou description hors feuille) : rien n'est compté deux fois.
  Prestation  : sommes de ses projets (dans une affaire).
  Affaire     : sommes de ses prestations cochées.

Statut d'un niveau (projet, prestation, affaire), avec S = le statut « Active la note de rendement » :
  - toutes ses descriptions ont S              -> S (statut final) ;
  - sinon, toutes ont le même statut           -> ce statut ;
  - sinon                                      -> progression « S x / n ».
Une description hors feuille n'a pas de statut : son niveau n'est donc pas terminé.

Temps d'une tâche (?tache=<id>) : somme des pointages de cette tâche sur le niveau, feuille ou non.
"""
from decimal import Decimal

from django.db.models import Count, F, Min, Q, Sum

from .models import Description, Statut

# Champ des parts de pointage pour chaque niveau
NIVEAUX_POINTAGE = {
    'description': 'description_id',
    'projet': 'description__projet_id',
    'prestation': 'description__projet__prestation_id',
    'affaire': 'description__projet__affaire_id',
}
TYPES_DANS_LES_FEUILLES = ('PRODUCTION', 'CONTROLE', 'REPRISE')

NIVEAUX = {
    # niveau : (champ des lignes de feuille, champ des descriptions)
    'description': ('description_id', 'id'),
    'projet': ('description__projet_id', 'projet_id'),
    'prestation': ('description__projet__prestation_id', 'projet__prestation_id'),
    'affaire': ('description__projet__affaire_id', 'projet__affaire_id'),
}


def _statut(statut):
    return {'id': statut.id, 'nom': statut.nom, 'couleur': statut.couleur}


def heures_pointees(niveau, ids, affaire_id=None, **filtre):
    """Heures pointées par niveau ({id: Decimal}), pour les parts de pointage qui respectent `filtre`."""
    from pointages.models import PartPointage   # pointages dépend de marches : import ici
    champ = NIVEAUX_POINTAGE[niveau]
    parts = PartPointage.objects.filter(**{f'{champ}__in': ids}, **filtre)
    if niveau == 'prestation':
        parts = parts.filter(description__projet__affaire_id=affaire_id)
    totaux = parts.values(champ).annotate(minutes=Sum(F('minutes_normales') + F('minutes_hs')))
    return {t[champ]: Decimal(t['minutes'] or 0) / 60 for t in totaux}


def heures_ajoutees_au_projet(niveau, ids, affaire_id=None):
    """Tâches « Ajouter au temps du projet » qui ne sont pas déjà comptées dans une ligne de feuille."""
    from pointages.models import PartPointage
    if niveau == 'description':
        return {}
    champ = NIVEAUX_POINTAGE[niveau]
    parts = (PartPointage.objects.filter(**{f'{champ}__in': ids}, pointage__tache__temps_projet=True)
             .exclude(ligne__isnull=False, pointage__tache__type__in=TYPES_DANS_LES_FEUILLES))
    if niveau == 'prestation':
        parts = parts.filter(description__projet__affaire_id=affaire_id)
    totaux = parts.values(champ).annotate(minutes=Sum(F('minutes_normales') + F('minutes_hs')))
    return {t[champ]: Decimal(t['minutes'] or 0) / 60 for t in totaux}


def resumes(niveau, ids, affaire_id=None, tache_id=None):
    """
    {id: {'temps': '12.50' | None, 'statut': {...} | None, 'temps_tache': '3.00' | None}}
    pour des descriptions, projets, prestations ou affaires.
    """
    from gsheets.models import LigneFeuille   # gsheets dépend de marches : import ici

    ids = list(ids)
    if not ids:
        return {}
    champ_ligne, champ_description = NIVEAUX[niveau]
    lignes = LigneFeuille.objects.filter(description__isnull=False, **{f'{champ_ligne}__in': ids})
    descriptions = Description.objects.filter(**{f'{champ_description}__in': ids})
    if niveau == 'prestation':   # une prestation se résume dans une affaire donnée
        lignes = lignes.filter(description__projet__affaire_id=affaire_id)
        descriptions = descriptions.filter(projet__affaire_id=affaire_id)

    cible = Statut.pour_note_rendement()
    agregats = {
        a[champ_ligne]: a for a in lignes.values(champ_ligne).annotate(
            prod=Sum('temps_prod'), controle=Sum('temps_controle'), reprise=Sum('temps_reprise'),
            avec_statut=Count('description', filter=Q(statut__isnull=False), distinct=True),
            au_statut=Count('description', filter=Q(statut=cible), distinct=True) if cible else Count('id', filter=Q(pk__in=[])),
            nb_statuts=Count('statut', distinct=True), un_statut=Min('statut_id'),
        )
    }
    totaux = dict(descriptions.values(champ_description).annotate(n=Count('id')).values_list(champ_description, 'n'))
    statuts = {s.id: s for s in Statut.objects.filter(pk__in={a['un_statut'] for a in agregats.values() if a['un_statut']})}

    ajoutees = heures_ajoutees_au_projet(niveau, ids, affaire_id)
    par_tache = heures_pointees(niveau, ids, affaire_id, pointage__tache_id=tache_id) if tache_id else {}
    deux = Decimal('0.01')

    resultat = {}
    for identifiant in ids:
        a = agregats.get(identifiant)
        total = totaux.get(identifiant, 0)
        temps = None
        a_du_temps = a and any(a[c] is not None for c in ('prod', 'controle', 'reprise'))
        if a_du_temps or identifiant in ajoutees:
            total_heures = sum((Decimal(a[c] or 0) for c in ('prod', 'controle', 'reprise')), Decimal(0)) if a else Decimal(0)
            temps = str((total_heures + ajoutees.get(identifiant, Decimal(0))).quantize(deux))
        statut = None
        if a and total:
            if cible and a['au_statut'] == total:
                statut = {**_statut(cible), 'final': True}
            elif a['avec_statut'] == total and a['nb_statuts'] == 1:
                commun = statuts.get(a['un_statut'])
                statut = {**_statut(commun), 'final': commun == cible} if commun else None
            elif cible and niveau != 'description':
                statut = {**_statut(cible), 'final': False, 'progression': {'au_statut': a['au_statut'], 'total': total}}
        temps_tache = None
        if tache_id:
            temps_tache = str(par_tache.get(identifiant, Decimal(0)).quantize(deux))
        resultat[identifiant] = {'temps': temps, 'statut': statut, 'temps_tache': temps_tache}
    return resultat


class SuiviMixin:
    """
    Ajoute à un serializer de liste les colonnes calculées « temps » et « statut ».
    Le calcul est fait une seule fois pour toute la page (quelques requêtes, quel que soit le nombre de lignes).
    """
    niveau_suivi = ''

    def _parametre(self, nom):
        request = self.context.get('request')
        valeur = request.query_params.get(nom) if request else None
        return int(valeur) if str(valeur or '').isdigit() else None

    def _affaire_suivi(self):
        return self._parametre('affaire')

    def _suivi(self, obj):
        cache = self.context.setdefault('_suivi', {})
        if obj.pk not in cache:
            parent = getattr(self, 'parent', None)
            objets = parent.instance if parent is not None and parent.instance is not None else [obj]
            ids = [o.pk for o in objets] if obj.pk in {o.pk for o in objets} else [obj.pk]
            cache.update(resumes(self.niveau_suivi, ids, self._affaire_suivi(), self._parametre('tache')))
        return cache.get(obj.pk, {'temps': None, 'statut': None, 'temps_tache': None})

    def get_temps(self, obj):
        return self._suivi(obj)['temps']

    def get_statut_suivi(self, obj):
        return self._suivi(obj)['statut']

    def get_temps_tache(self, obj):
        return self._suivi(obj)['temps_tache']
