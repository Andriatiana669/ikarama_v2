# backend/gsheets/services.py
"""
Règles des feuilles : qui y a accès, et synchronisation des lignes avec le Marché.
"""
from django.db import transaction
from django.db.models import Exists, Max, OuterRef, ProtectedError, Q

from autorisations.permissions import est_administrateur
from marches.models import Affaire, Description, Statut

from .models import Feuille, LigneFeuille, NoteCritere

# ------------------------------------------------------------------
# Accès
# ------------------------------------------------------------------
def feuilles_de(employe):
    """Feuilles dont la personne est créatrice, responsable ou membre d'une des affaires."""
    if employe is None:
        return Feuille.objects.none()
    return Feuille.objects.filter(
        Q(cree_par=employe) | Q(perimetres__affaire__responsables=employe) | Q(perimetres__affaire__membres=employe)
    ).distinct()


def peut_gerer(user, feuille):
    """Créateur, responsable d'une des affaires de la feuille, ou administrateur."""
    moi = getattr(user, 'employe', None)
    if est_administrateur(user):
        return True
    if moi is None:
        return False
    return feuille.cree_par_id == moi.pk or feuille.perimetres.filter(affaire__responsables=moi).exists()


def est_concerne(user, feuille):
    """Responsable ou membre d'une des affaires de la feuille (ou créateur, ou administrateur)."""
    moi = getattr(user, 'employe', None)
    return peut_gerer(user, feuille) or bool(moi and feuille.perimetres.filter(affaire__membres=moi).exists())


def personnes_de_l_affaire(affaire):
    """Responsables et membres : les seules personnes proposées dans les colonnes Employé / Contrôleur / Reprise."""
    return (affaire.responsables.all() | affaire.membres.all()).distinct().order_by('nom', 'prenom')


def affaires_creables(employe, user=None):
    """
    Affaires actives où l'on peut créer une feuille : droit « Créer » de Google Sheet > Mes feuilles
    (Paramètres > Autorisation ; par défaut, les affaires dont on est responsable).
    """
    from autorisations.droits import q_droit
    affaires = Affaire.objects.filter(actif=True).prefetch_related('liens_prestations__prestation')
    if user is not None:
        return affaires.filter(q_droit(user, 'gsheets_feuilles', 'creer')).distinct()
    return affaires.filter(responsables=employe)


def feuilles_visibles(user):
    """
    Feuilles affichées dans Mes feuilles : celles des affaires du périmètre « Voir » de Google Sheet > Mes feuilles
    (par défaut : les affaires dont on est responsable ou membre ; d'autres affaires seulement par un rôle).
    """
    from autorisations.droits import q_droit
    return Feuille.objects.filter(q_droit(user, 'gsheets_feuilles', 'voir', 'perimetres__affaire__')).distinct()


def droit_feuille(user, feuille, action):
    """
    Droit « action » (modifier, supprimer…) de Google Sheet > Mes feuilles sur UNE FEUILLE (pas sur ses données) :
    au moins une de ses affaires dans le périmètre du rôle. Un refus total l'emporte toujours.
    """
    from autorisations.droits import peut, q_droit
    if est_administrateur(user):
        return True
    if not peut(user, 'gsheets_feuilles', action):
        return False
    return Affaire.objects.filter(perimetres_feuilles__feuille=feuille).filter(q_droit(user, 'gsheets_feuilles', action)).exists()


def verifier_droit_feuille(user, feuille, action):
    from autorisations.droits import ACTIONS
    from autorisations.permissions import DroitManquant
    if not droit_feuille(user, feuille, action):
        raise DroitManquant(f"Vous n’avez pas le droit « {ACTIONS[action]} » sur la feuille « {feuille.nom} ».")


# ------------------------------------------------------------------
# Synchronisation des lignes
# ------------------------------------------------------------------
def instantane(description):
    projet = description.projet
    return {
        'num_affaire': projet.affaire.num_affaire,
        'nom_affaire': projet.affaire.nom,
        'affaire_id': projet.affaire_id,
        'prestation': projet.prestation.nom,
        'unite': projet.prestation.unite,
        'projet': projet.nom,
        'description': description.nom,
        'quantite': str(description.quantite) if description.quantite is not None else None,
        'rendement_objectif': str(projet.rendement.valeur),
        'date_livraison': projet.date_livraison.isoformat(),
    }


def descriptions_du_perimetre(feuille):
    q = Q(pk__in=[])
    for p in feuille.perimetres.all():
        q |= Q(projet__affaire_id=p.affaire_id, projet__prestation_id=p.prestation_id)
    return (Description.objects.filter(q)
            .select_related('projet__affaire', 'projet__prestation', 'projet__rendement')
            .order_by('projet__affaire__ordre', 'projet__affaire_id', 'projet__prestation__ordre',
                      'projet__ordre', 'projet_id', 'ordre', 'id'))


@transaction.atomic
def synchroniser(feuille):
    """
    Une ligne par description du périmètre :
      - les nouvelles descriptions reçoivent une ligne (numérotée à la suite) ;
      - les lignes d'une prestation retirée du périmètre sont supprimées.
    Les lignes d'une description supprimée du Marché restent (description = vide, « retirée »).
    """
    descriptions = list(descriptions_du_perimetre(feuille))
    ids = {d.pk for d in descriptions}
    feuille.lignes.exclude(description__isnull=True).exclude(description_id__in=ids).delete()

    existantes = set(feuille.lignes.exclude(description__isnull=True).values_list('description_id', flat=True))
    numero = feuille.lignes.aggregate(m=Max('numero'))['m'] or 0
    statut_defaut = Statut.defaut()   # case « Par défaut » du tableau Statuts
    nouvelles = []
    for d in descriptions:
        if d.pk not in existantes:
            numero += 1
            nouvelles.append(LigneFeuille(feuille=feuille, numero=numero, description=d, instantane=instantane(d),
                                          statut=statut_defaut))
    # Date de début des nouvelles lignes : première date déjà pointée pour leur description
    if nouvelles:
        from django.db.models import Min

        from pointages.models import PartPointage
        dates = dict(PartPointage.objects.filter(description_id__in=[l.description_id for l in nouvelles])
                     .values_list('description_id').annotate(d=Min('pointage__date')))
        for ligne in nouvelles:
            ligne.date_debut = dates.get(ligne.description_id)
    LigneFeuille.objects.bulk_create(nouvelles)
    if nouvelles:
        from temps_reel.diffusion import feuille_modifiee
        feuille_modifiee(feuille.pk)   # nouvelles lignes : les pages ouvertes le savent aussitôt
    return len(nouvelles)


def feuilles_concernees(description):
    projet = description.projet
    return Feuille.objects.filter(perimetres__affaire_id=projet.affaire_id,
                                  perimetres__prestation_id=projet.prestation_id).distinct()


# ------------------------------------------------------------------
# Suppression d'une description du Marché
# ------------------------------------------------------------------
class DonneesSaisiesProtegees(ProtectedError):
    """Suppression refusée : une ligne de feuille contient déjà des données saisies."""


def q_ligne_avec_donnees():
    """
    Une ligne « a des données » dès qu'une saisie y a été faite : personne choisie, avancement,
    commentaire, reprises, note de critère, temps ou date du Pointage, ou un statut autre que
    le statut par défaut (mis automatiquement à la création de la ligne).
    """
    statut_defaut = Statut.defaut()
    statut = ~Q(statut__isnull=True) & ~Q(statut=statut_defaut) if statut_defaut else ~Q(statut__isnull=True)
    note = Exists(NoteCritere.objects.filter(ligne=OuterRef('pk'), note__isnull=False))
    return (Q(employe__isnull=False) | Q(controleur__isnull=False) | Q(employe_reprise__isnull=False)
            | Q(avancement__gt=0) | ~Q(commentaires='') | ~Q(commentaires_controle='') | ~Q(commentaires_reprise='')
            | Q(nb_reprises__gt=0)
            | Q(temps_prod__isnull=False) | Q(temps_controle__isnull=False) | Q(temps_reprise__isnull=False)
            | Q(date_debut__isnull=False) | statut | Q(note))


def preparer_suppression_description(description):
    """
    Avant de supprimer une description du Marché :
      - si une de ses lignes de feuille contient des données -> refus (DonneesSaisiesProtegees) ;
      - sinon ses lignes (vides) sont supprimées des feuilles.
    """
    lignes = LigneFeuille.objects.filter(description=description)
    pleines = list(lignes.filter(q_ligne_avec_donnees()).select_related('feuille').order_by('feuille__nom', 'numero'))
    if pleines:
        endroits = ', '.join(f"« {l.feuille.nom} » (ligne {l.numero})" for l in pleines[:5])
        if len(pleines) > 5:
            endroits += f' et {len(pleines) - 5} autre(s)'
        raise DonneesSaisiesProtegees(
            f"Impossible de supprimer la description « {description.nom} » : des données ont déjà été saisies "
            f"dans la feuille {endroits}. Videz d'abord ces lignes.",
            pleines,
        )
    lignes.delete()



# ------------------------------------------------------------------
# Temps Estimatif : couleur d'alerte d'une ligne (feuille, notifications, accueil)
# ------------------------------------------------------------------
def niveau_alerte(estimatif_heures, temps_prod, statut_id, reglages, statut_final):
    """'rouge' (Temps de prod ≥ estimatif), 'orange' (≥ (100 − marge) %), ou None (rien, ou statut final)."""
    from decimal import Decimal
    if estimatif_heures is None or temps_prod is None or (statut_final and statut_id == statut_final.id):
        return None
    if temps_prod >= estimatif_heures:
        return 'rouge'
    if temps_prod >= estimatif_heures * (Decimal(100 - reglages.marge) / 100):
        return 'orange'
    return None


def alerte_ligne(ligne):
    """Couleur d'alerte d'une ligne liée au Marché (même règle que la colonne Temps Estimatif)."""
    from decimal import Decimal

    from marches.models import Statut
    from rendements.models import ParametresRendement

    from .models import ParametresTempsEstimatif
    if ligne.description_id is None:
        return None
    description = ligne.description
    objectif = description.projet.rendement.valeur if description.projet.rendement_id else None
    if not description.quantite or not objectif:
        return None
    estimatif = Decimal(description.quantite) / Decimal(objectif) * ParametresRendement.actuels().heures_par_jour
    return niveau_alerte(estimatif, ligne.temps_prod, ligne.statut_id, ParametresTempsEstimatif.actuels(),
                         Statut.pour_note_rendement())
