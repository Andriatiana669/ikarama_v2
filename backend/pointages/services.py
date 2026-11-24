# backend/pointages/services.py
"""
Règles du pointage et lien avec les feuilles (gsheets).

  Type de tâche -> colonnes de la feuille :
      PRODUCTION -> Employé          + Temps de prod      + Commentaires
      CONTROLE   -> Contrôleur        + Temps de contrôle  + Commentaires contrôle
      REPRISE    -> Employé reprise   + Temps de reprise   + Commentaires reprise

  - On pointe une ou plusieurs Descriptions de ses affaires (responsable ou membre), même hors feuille.
    Plusieurs descriptions : seulement pour une tâche « Plusieurs descriptions », dans un même projet ;
    le temps est partagé au prorata de leurs quantités (à parts égales si une quantité manque).
  - Chaque description présente dans une feuille est rattachée à sa ligne (une Affaire + Prestation
    n'est que dans une seule feuille) ; hors feuille, le temps est seulement enregistré.
  - Si la case (Employé / Contrôleur / Employé reprise) est vide, on y est placé automatiquement ;
    si quelqu'un d'autre y est déjà, le pointage est refusé. Une fois pointée, la case est verrouillée.
  - Les temps de la feuille = somme des parts de temps des pointages de ce type sur la ligne ;
    la Date de début = premier jour pointé sur la ligne.
  - Le commentaire d'un pointage est ajouté à la suite dans la colonne de commentaires du type.
  - Supprimer (ou déplacer) un pointage retire son commentaire de la feuille, et retire la personne
    de la colonne si elle n'a plus aucun pointage de ce type sur la ligne.
"""
from decimal import ROUND_DOWN, Decimal

from django.db import transaction
from django.db.models import Min, Q, Sum
from rest_framework import serializers

from gsheets.models import HistoriqueLigne, LigneFeuille
from marches.models import Affaire, Description

from .calculs import repartir_journee
from .models import PartPointage, Pointage

COLONNES = {
    'PRODUCTION': ('employe', 'temps_prod', 'Employé'),
    'CONTROLE': ('controleur', 'temps_controle', 'Contrôleur'),
    'REPRISE': ('employe_reprise', 'temps_reprise', 'Employé reprise'),
}
COMMENTAIRES = {
    'PRODUCTION': ('commentaires', 'Commentaires'),
    'CONTROLE': ('commentaires_controle', 'Commentaires contrôle'),
    'REPRISE': ('commentaires_reprise', 'Commentaires reprise'),
}
SEPARATEUR = ' | '


# ------------------------------------------------------------------
# Ce que la personne peut pointer
# ------------------------------------------------------------------
def affaires_pointables(employe):
    """Affaires actives dont la personne est responsable ou membre."""
    if employe is None:
        return Affaire.objects.none()
    return Affaire.objects.filter(actif=True).filter(Q(responsables=employe) | Q(membres=employe)).distinct()


def descriptions_pointables(employe):
    return Description.objects.filter(projet__affaire__in=affaires_pointables(employe))


def q_place(employe, prefixe=''):
    """Lignes où la personne est Employé, Contrôleur ou Employé reprise."""
    return Q(**{f'{prefixe}employe': employe}) | Q(**{f'{prefixe}controleur': employe}) | Q(**{f'{prefixe}employe_reprise': employe})


def ligne_pour(description, tache, employe):
    """
    La ligne de feuille qui reçoit le temps d'une description (None si elle n'est dans aucune feuille).
    S'il en existe plusieurs (anciennes feuilles en double) : celle où la personne est placée
    pour ce type de tâche, sinon celle de la feuille la plus récente.
    """
    lignes = list(LigneFeuille.objects.filter(description=description).select_related('feuille')
                  .order_by('-feuille__cree_le', '-feuille_id'))
    if len(lignes) <= 1:
        return lignes[0] if lignes else None
    if tache.type in COLONNES:
        champ = COLONNES[tache.type][0]
        for ligne in lignes:
            if getattr(ligne, f'{champ}_id') == employe.pk:
                return ligne
    return lignes[0]


def colonnes_verrouillees(ligne):
    """Colonnes de personnes qui ne peuvent plus changer dans la feuille, car déjà pointées."""
    types = {part.pointage.tache.type for part in ligne.parts_pointage.all()}   # préchargé par la feuille
    return [COLONNES[t][0] for t in types if t in COLONNES]


# ------------------------------------------------------------------
# Partage du temps entre plusieurs descriptions
# ------------------------------------------------------------------
def parts_au_prorata(descriptions):
    """
    Part de chaque description (somme = 1) : au prorata des quantités,
    à parts égales si une quantité manque ou vaut 0. Renvoie (parts, au_prorata).
    """
    quantites = [d.quantite for d in descriptions]
    au_prorata = all(q is not None and q > 0 for q in quantites)
    if not au_prorata:
        quantites = [Decimal(1)] * len(descriptions)
    total = sum(quantites)
    parts = [(q / total).quantize(Decimal('0.000001'), rounding=ROUND_DOWN) for q in quantites]
    parts[-1] += Decimal(1) - sum(parts)   # le reste d'arrondi va à la dernière
    return parts, au_prorata


def repartir_minutes(total, parts):
    """Partage des minutes entières entre des parts (méthode des plus forts restes : la somme est exacte)."""
    bruts = [Decimal(total) * p for p in parts]
    entiers = [int(b) for b in bruts]
    reste = total - sum(entiers)
    for i in sorted(range(len(parts)), key=lambda i: bruts[i] - entiers[i], reverse=True)[:reste]:
        entiers[i] += 1
    return entiers


# ------------------------------------------------------------------
# Contrôles
# ------------------------------------------------------------------
def verifier_chevauchement(employe, date, debut, fin, sauf=None):
    autres = Pointage.objects.filter(employe=employe, date=date, heure_debut__lt=fin, heure_fin__gt=debut)
    if sauf is not None:
        autres = autres.exclude(pk=sauf)
    autre = autres.first()
    if autre:
        raise serializers.ValidationError(
            f"Ce créneau chevauche un autre pointage ({autre.heure_debut:%H:%M}–{autre.heure_fin:%H:%M}).")


def verifier_descriptions(descriptions, tache):
    if not descriptions:
        raise serializers.ValidationError({'descriptions': 'Choisissez au moins une description.'})
    if len(descriptions) > 1:
        if not tache.plusieurs_descriptions:
            raise serializers.ValidationError(
                {'descriptions': f"La tâche « {tache.nom} » ne permet qu'une seule description."})
        if len({d.projet_id for d in descriptions}) > 1:
            raise serializers.ValidationError(
                {'descriptions': 'Les descriptions doivent appartenir au même projet / à la même commune.'})


def placer_sur_la_ligne(ligne, tache, employe):
    """Place la personne dans la colonne de la tâche, ou refuse si quelqu'un d'autre y est."""
    if ligne is None or tache.type not in COLONNES:
        return
    champ, _, libelle = COLONNES[tache.type]
    actuel_id = getattr(ligne, f'{champ}_id')
    if actuel_id is None:
        setattr(ligne, champ, employe)
        ligne.modifie_par = employe
        ligne.save(update_fields=[champ, 'modifie_par', 'modifie_le'])
        HistoriqueLigne.objects.create(feuille_id=ligne.feuille_id, ligne=ligne, champ=champ, libelle=libelle,
                                       ancienne_valeur='', nouvelle_valeur=f'{employe.identifiant} (pointage)',
                                       auteur=employe)
    elif actuel_id != employe.pk:
        autre = getattr(ligne, champ)
        description = ligne.description.nom if ligne.description else ''
        raise serializers.ValidationError(
            f"{autre.identifiant} est déjà placé(e) comme « {libelle} » sur la ligne « {description} » : "
            f"la tâche « {tache.nom} » ne peut pas y être pointée par vous.")


def fragment_commentaire(employe, date, texte):
    """Texte ajouté dans la feuille pour un commentaire de pointage (vide s'il n'y a pas de commentaire)."""
    texte = ' '.join((texte or '').split())
    return f"{date:%d/%m} {employe.identifiant} : {texte}" if texte else ''


def ajouter_commentaire(ligne, type_tache, employe, fragment):
    """Ajoute le fragment à la suite dans la colonne de commentaires du type de tâche."""
    if ligne is None or not fragment or type_tache not in COMMENTAIRES:
        return
    champ, libelle = COMMENTAIRES[type_tache]
    ancien = getattr(ligne, champ) or ''
    nouveau = f"{ancien}{SEPARATEUR}{fragment}" if ancien.strip() else fragment
    _changer(ligne, champ, libelle, ancien, nouveau, employe)


def retirer_commentaire(ligne, type_tache, employe, fragment):
    """Retire le fragment de la colonne de commentaires (s'il n'a pas été modifié à la main entre-temps)."""
    if ligne is None or not fragment or type_tache not in COMMENTAIRES:
        return
    champ, libelle = COMMENTAIRES[type_tache]
    ancien = getattr(ligne, champ) or ''
    morceaux = [m.strip() for m in ancien.split(SEPARATEUR.strip())]
    if fragment not in morceaux:
        return
    morceaux.remove(fragment)
    _changer(ligne, champ, libelle, ancien, SEPARATEUR.join(m for m in morceaux if m), employe)


def liberer_colonne(ligne, type_tache, employe):
    """Retire la personne de la colonne de la tâche si elle n'a plus aucun pointage de ce type sur la ligne."""
    if ligne is None or type_tache not in COLONNES:
        return
    champ, _, libelle = COLONNES[type_tache]
    if getattr(ligne, f'{champ}_id') != employe.pk:
        return
    if ligne.parts_pointage.filter(pointage__employe=employe, pointage__tache__type=type_tache).exists():
        return
    _changer(ligne, champ, libelle, employe, None, employe, texte_ancien=employe.identifiant,
             texte_nouveau='(pointage supprimé)')


def _changer(ligne, champ, libelle, ancien, nouveau, auteur, texte_ancien=None, texte_nouveau=None):
    setattr(ligne, champ, nouveau)
    ligne.modifie_par = auteur
    ligne.save(update_fields=[champ, 'modifie_par', 'modifie_le'])
    HistoriqueLigne.objects.create(feuille_id=ligne.feuille_id, ligne=ligne, champ=champ, libelle=libelle,
                                   ancienne_valeur=texte_ancien if texte_ancien is not None else ancien,
                                   nouvelle_valeur=texte_nouveau if texte_nouveau is not None else (nouveau or ''),
                                   auteur=auteur)


def retirer_de_la_feuille(pointage_infos, employe):
    """
    À appeler APRÈS avoir supprimé / modifié le pointage :
    pointage_infos = (type de tâche, fragment de commentaire, ids des lignes).
    """
    type_tache, fragment, lignes = pointage_infos
    for ligne in LigneFeuille.objects.filter(pk__in=lignes):
        retirer_commentaire(ligne, type_tache, employe, fragment)
        liberer_colonne(ligne, type_tache, employe)


def infos_pour_retrait(pointage):
    return (pointage.tache.type, pointage.fragment_commentaire,
            set(pointage.parts.exclude(ligne__isnull=True).values_list('ligne_id', flat=True)))


# ------------------------------------------------------------------
# Enregistrement des parts et recalculs
# ------------------------------------------------------------------
def enregistrer_parts(pointage, descriptions):
    """Remplace les parts du pointage. Renvoie les lignes concernées (avant et après)."""
    anciennes = set(pointage.parts.exclude(ligne__isnull=True).values_list('ligne_id', flat=True))
    pointage.parts.all().delete()
    parts, _ = parts_au_prorata(descriptions)
    nouvelles = []
    for description, part in zip(descriptions, parts):
        ligne = ligne_pour(description, pointage.tache, pointage.employe)
        placer_sur_la_ligne(ligne, pointage.tache, pointage.employe)
        nouvelles.append(PartPointage(pointage=pointage, description=description, ligne=ligne, part=part))
    PartPointage.objects.bulk_create(nouvelles)
    return anciennes | {p.ligne_id for p in nouvelles if p.ligne_id}


def recalculer_journee(employe_id, date):
    """H_Durée et HS de chaque pointage de la journée, puis partage entre ses descriptions."""
    pointages = list(Pointage.objects.filter(employe_id=employe_id, date=date).prefetch_related('parts'))
    repartition = repartir_journee(date, pointages)
    a_modifier, parts_a_modifier = [], []
    for p in pointages:
        normales, hs = repartition[id(p)]
        if (p.minutes_normales, p.minutes_hs) != (normales, hs):
            p.minutes_normales, p.minutes_hs = normales, hs
            a_modifier.append(p)
        parts = list(p.parts.all())
        if parts:
            coefficients = [part.part for part in parts]
            for part, n, h in zip(parts, repartir_minutes(normales, coefficients), repartir_minutes(hs, coefficients)):
                if (part.minutes_normales, part.minutes_hs) != (n, h):
                    part.minutes_normales, part.minutes_hs = n, h
                    parts_a_modifier.append(part)
    Pointage.objects.bulk_update(a_modifier, ['minutes_normales', 'minutes_hs'])
    PartPointage.objects.bulk_update(parts_a_modifier, ['minutes_normales', 'minutes_hs'])


def premiere_date_pointee(description_id):
    """Date de début : première date pointée pour la description (toutes tâches, toutes personnes)."""
    if not description_id:
        return None
    return PartPointage.objects.filter(description_id=description_id).aggregate(d=Min('pointage__date'))['d']


def recalculer_ligne(ligne_id):
    """
    Temps de prod / contrôle / reprise de la ligne = somme des parts de temps de chaque type (en heures) ;
    Date de début = première date pointée pour sa description.
    """
    ligne = (LigneFeuille.objects.filter(pk=ligne_id)
             .select_related('feuille', 'description__projet__affaire', 'description__projet__rendement').first())
    if ligne is None:
        return
    from gsheets.services import alerte_ligne
    alerte_avant = alerte_ligne(ligne)
    # Date de début : premier jour pointé pour la description (y compris avant la création de la feuille)
    ligne.date_debut = premiere_date_pointee(ligne.description_id)
    for type_tache, (_, champ_temps, _) in COLONNES.items():
        parts = ligne.parts_pointage.filter(pointage__tache__type=type_tache)
        if parts.exists():
            total = parts.aggregate(n=Sum('minutes_normales'), h=Sum('minutes_hs'))
            minutes = (total['n'] or 0) + (total['h'] or 0)
            setattr(ligne, champ_temps, (Decimal(minutes) / 60).quantize(Decimal('0.01')))
        else:
            setattr(ligne, champ_temps, None)
    ligne.save(update_fields=['date_debut', 'temps_prod', 'temps_controle', 'temps_reprise', 'modifie_le'])
    signaler_alerte(ligne, alerte_avant, alerte_ligne(ligne))


def signaler_alerte(ligne, avant, apres):
    """Notifie l'Employé et les responsables quand une ligne passe à l'orange ou au rouge (Temps Estimatif)."""
    if apres is None or apres == avant or avant == 'rouge':
        return
    from notifications.services import notifier
    affaire = ligne.description.projet.affaire
    destinataires = [ligne.employe_id, *affaire.responsables.values_list('pk', flat=True)]
    etat = 'a dépassé' if apres == 'rouge' else 'approche'
    notifier(destinataires, 'temps_estimatif',
             f"« {ligne.description.nom} » {etat} son Temps Estimatif",
             message=f"{affaire.nom}, feuille « {ligne.feuille.nom} », ligne {ligne.numero} : {ligne.temps_prod} h de production.",
             lien=f'/google-sheet/feuilles/{ligne.feuille_id}', cle=f'alerte-{ligne.pk}-{apres}')


@transaction.atomic
def apres_modification(journees, lignes):
    """Recalcule les journées (employé, date) puis les lignes touchées par un ajout / modification / suppression."""
    for employe_id, date in set(journees):
        recalculer_journee(employe_id, date)
    for ligne_id in {l for l in lignes if l}:
        recalculer_ligne(ligne_id)
