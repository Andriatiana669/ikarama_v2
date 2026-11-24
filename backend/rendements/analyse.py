# backend/rendements/analyse.py
"""
Page Rendement : rendement réel comparé au rendement objectif.

Sélection : affaires, prestations, projets / communes (cases à cocher), statut du projet (statut calculé
du Marché), période (sur la date des pointages) et tâches (SEULES les tâches cochées comptent dans le temps ;
aucune cochée = toutes). Sans affaire cochée, il n'y a rien à afficher.

Barres du graphique : le niveau en dessous de la sélection (plusieurs éléments cochés = additionnés) :
  affaire(s)                -> une barre par prestation
  + prestation(s)           -> une barre par projet / commune
  + projet(s) / commune(s)  -> une barre par description
Chaque barre garde l'unité de sa prestation. Le global (barre « Global », rendement des équipes,
personnes) n'est calculé que si toutes les prestations concernées ont la même unité.

  Rendement d'un projet     = Quantité du projet ÷ temps pointé sur le projet × heures par jour
  Rendement des équipes     = Σ Quantité des projets ÷ Σ temps pointé × heures par jour
  Rendement d'une personne  = Quantité des descriptions où elle est « Employé » dans la feuille
                              ÷ son temps pointé sur la sélection × heures par jour
  Évolution (jour / mois)   : la quantité d'une description, qui n'a pas de date, est répartie sur les
                              périodes au prorata du temps que la personne y a pointé.
  Objectif d'un projet = son rendement objectif par jour ; objectif des équipes = moyenne pondérée
  par les quantités. « heures par jour » : Paramètres > Rendement & Note.
"""
from collections import defaultdict
from decimal import Decimal

from django.db.models import Q

from autorisations.permissions import est_administrateur
from gsheets.models import LigneFeuille
from marches.models import Affaire, Description, Projet
from marches.suivi import resumes
from pointages.models import PartPointage

from .models import ParametresRendement


def ids(valeur):
    return [int(v) for v in str(valeur or '').split(',') if v.strip().isdigit()]


def affaires_visibles(user):
    """Superadmin : toutes les affaires en cours ; sinon celles dont on est responsable ou membre."""
    affaires = Affaire.objects.filter(actif=True)
    if est_administrateur(user):
        return affaires
    moi = getattr(user, 'employe', None)
    return affaires.filter(Q(responsables=moi) | Q(membres=moi)).distinct() if moi else affaires.none()


def rendement(quantite, minutes, heures_par_jour):
    if not quantite or not minutes:
        return None
    return float(Decimal(quantite) / (Decimal(minutes) / 60) * heures_par_jour)


# ----------------------------------------------------------------------
# Source du temps : pointages (par défaut) ou feuilles (« Données des feuilles »)
# ----------------------------------------------------------------------
from types import SimpleNamespace

COLONNES_FEUILLE = {
    # type de tâche : (colonne de temps, personne de la ligne, libellé)
    'PRODUCTION': ('temps_prod', 'employe', 'Temps de prod'),
    'CONTROLE': ('temps_controle', 'controleur', 'Temps de contrôle'),
    'REPRISE': ('temps_reprise', 'employe_reprise', 'Temps de reprise'),
}


def mode_feuilles(parametres):
    """« Données des feuilles » : demandé par la page (?source=feuilles) ET autorisé dans Paramètres > Graphiques."""
    if parametres.get('source') != 'feuilles':
        return False
    from .models import ParametresGraphiques
    return ParametresGraphiques.actuels().donnees_feuilles


def mode_pointages(parametres):
    """
    « Données des pointages » : demandé par la page (?source=pointages) ET autorisé dans Paramètres > Graphiques.
    Les descriptions viennent des pointages (même sans feuille) ; la quantité revient à la personne qui y a
    pointé le plus de temps de Production ; la « date de début » est le premier jour pointé.
    """
    if parametres.get('source') != 'pointages':
        return False
    from .models import ParametresGraphiques
    return ParametresGraphiques.actuels().donnees_pointages


def _lignes_des_pointages(projet_ids):
    """Une ligne calculée par description pointée : comme une ligne de feuille (description, Employé, date de début)."""
    parts = (PartPointage.objects.filter(description__projet_id__in=list(projet_ids))
             .select_related('pointage__employe', 'pointage__tache', 'description'))
    production = defaultdict(lambda: defaultdict(int))
    toutes = defaultdict(lambda: defaultdict(int))
    premiere = {}
    personnes, descriptions = {}, {}
    for part in parts:
        d, employe = part.description_id, part.pointage.employe
        minutes = part.minutes_normales + part.minutes_hs
        personnes[employe.pk] = employe
        descriptions[d] = part.description
        toutes[d][employe.pk] += minutes
        if part.pointage.tache.type == 'PRODUCTION':
            production[d][employe.pk] += minutes
        if d not in premiere or part.pointage.date < premiere[d]:
            premiere[d] = part.pointage.date
    lignes = []
    for d, description in descriptions.items():
        temps = production[d] or toutes[d]
        employe = personnes[max(temps, key=temps.get)]
        lignes.append(SimpleNamespace(description_id=d, description=description, employe=employe, employe_id=employe.pk,
                                      date_debut=premiere[d], commentaires='', commentaires_controle='', statut_id=None))
    return lignes


def lignes_selection(projet_ids, parametres):
    """
    Les lignes de la sélection (vraies lignes de feuille, ou lignes calculées depuis les pointages en mode
    « Données des pointages »), après la période (Du… Au…), les commentaires et les mois.
    Renvoie (lignes, mois proposés avant le choix des mois).
    """
    from datetime import date as Date
    debut = Date.fromisoformat(parametres['debut']) if parametres.get('debut') else None
    fin = Date.fromisoformat(parametres['fin']) if parametres.get('fin') else None
    if mode_pointages(parametres):
        lignes = _lignes_des_pointages(projet_ids)
        lignes = [l for l in lignes if (not debut or l.date_debut >= debut) and (not fin or l.date_debut <= fin)]
        # Pas de commentaires sans feuille : seule la case « Sans commentaire » garde des lignes
        for champ in ('commentaires', 'commentaires_controle'):
            coches = _liste_cochee(parametres.get(champ))
            if coches and SANS_COMMENTAIRE not in coches:
                lignes = []
    else:
        qs = LigneFeuille.objects.filter(description__projet_id__in=list(projet_ids)).select_related('employe', 'description')
        if debut:
            qs = qs.filter(date_debut__gte=debut)
        if fin:
            qs = qs.filter(date_debut__lte=fin)
        lignes = list(filtrer_commentaires(qs, parametres))
    mois_disponibles = sorted({l.date_debut.strftime('%Y-%m') for l in lignes if l.date_debut}, reverse=True)
    mois_choisis = {m for m in str(parametres.get('mois') or '').split(',') if len(m) == 7}
    if mois_choisis:
        lignes = [l for l in lignes if l.date_debut and l.date_debut.strftime('%Y-%m') in mois_choisis]
    return lignes, mois_disponibles


def temps_pointes(parametres, **filtre_description):
    """
    Les éléments de temps de la sélection, avec l'interface d'une part de pointage
    (description_id, minutes_normales, minutes_hs, pointage.employe / tache / date, description).

      Pointages : les parts de pointage (temps réel, daté au jour, par tâche).
      Feuilles  : pour chaque ligne, Temps de prod (Employé), Temps de contrôle (Contrôleur), Temps de reprise
                  (Employé reprise), tâche = le TYPE (Production, Contrôle, Reprise), date = Date de début.
    filtre_description : filtre sur la description (ex. projet_id__in=…, pk__in=…).
    """
    filtre = {f'description__{cle}': valeur for cle, valeur in filtre_description.items()}
    if not mode_feuilles(parametres):
        parts = list(PartPointage.objects.filter(**filtre).select_related('pointage__employe', 'pointage__tache', 'description'))
        if mode_pointages(parametres):
            # Données des pointages : seulement le temps de la personne à qui revient la description
            proprietaires = {l.description_id: l.employe_id
                             for l in _lignes_des_pointages({p.description.projet_id for p in parts})}
            parts = [p for p in parts if proprietaires.get(p.description_id) == p.pointage.employe_id]
        return parts
    elements = []
    lignes = (LigneFeuille.objects.filter(description__isnull=False, **filtre)
              .select_related('description', 'employe', 'controleur', 'employe_reprise'))
    for ligne in lignes:
        for type_tache, (colonne, personne, libelle) in COLONNES_FEUILLE.items():
            temps, employe = getattr(ligne, colonne), getattr(ligne, personne)
            if not temps or employe is None:
                continue
            tache = SimpleNamespace(id=type_tache, nom=libelle, type=type_tache)
            elements.append(SimpleNamespace(
                source='feuille', description_id=ligne.description_id, description=ligne.description, ligne_id=ligne.id,
                minutes_normales=int(round(temps * 60)), minutes_hs=0,
                pointage=SimpleNamespace(employe=employe, employe_id=employe.id, tache=tache, tache_id=type_tache,
                                         date=ligne.date_debut),
            ))
    return elements


def filtrer_taches(elements, taches_ids):
    """Garde le temps des tâches choisies ; en mode feuilles, par TYPE de tâche (Production, Contrôle, Reprise)."""
    if not taches_ids:
        return list(elements)
    from marches.models import Tache
    types = set(Tache.objects.filter(pk__in=taches_ids).values_list('type', flat=True))
    return [e for e in elements
            if (e.pointage.tache.type in types if getattr(e, 'source', None) == 'feuille' else e.pointage.tache_id in taches_ids)]


def dates(elements):
    """Seulement les éléments datés (en mode feuilles, une ligne sans Date de début n'a pas de date)."""
    return [e for e in elements if e.pointage.date is not None]


SANS_COMMENTAIRE = '__sans__'


def _liste_cochee(valeur):
    """Liste cochée envoyée par l'écran en JSON (les commentaires peuvent contenir des virgules)."""
    import json
    if not valeur:
        return []
    try:
        liste = json.loads(valeur)
    except (TypeError, ValueError):
        return []
    return [str(v) for v in liste] if isinstance(liste, list) else []


def filtrer_commentaires(lignes, parametres):
    """
    Filtres « Commentaires » et « Commentaires contrôle » des onglets du Rendement (listes à cocher) :
    une case = un commentaire complet tel qu'écrit dans la feuille, ou « Sans commentaire ».
    Aucune case cochée : pas de filtre. Seules les lignes de feuille concernées comptent ensuite.
    """
    for champ in ('commentaires', 'commentaires_controle'):
        coches = _liste_cochee(parametres.get(champ))
        if not coches:
            continue
        q = Q(**{f'{champ}__in': [c for c in coches if c != SANS_COMMENTAIRE]})
        if SANS_COMMENTAIRE in coches:
            q |= Q(**{f'{champ}__isnull': True}) | Q(**{champ: ''})
        lignes = lignes.filter(q)
    return lignes


def commentaires_proposes(projets):
    """Les commentaires (complets, distincts) des lignes de feuille de la sélection, pour les listes à cocher."""
    lignes = LigneFeuille.objects.filter(description__projet__in=projets)
    resultat = {}
    for champ in ('commentaires', 'commentaires_controle'):
        valeurs = (lignes.exclude(**{f'{champ}__isnull': True}).exclude(**{champ: ''})
                   .values_list(champ, flat=True).distinct().order_by(champ)[:500])
        resultat[champ] = ([{'id': SANS_COMMENTAIRE, 'nom': 'Sans commentaire'}]
                           + [{'id': v, 'nom': v} for v in valeurs])
    return resultat


def projets_selectionnes(user, parametres):
    """Projets de la sélection. Aucune affaire cochée : toutes les affaires visibles (une prestation seule suffit)."""
    projets = Projet.objects.filter(affaire__in=affaires_visibles(user)).select_related('affaire', 'prestation', 'rendement')
    if ids(parametres.get('affaires')):
        projets = projets.filter(affaire_id__in=ids(parametres['affaires']))
    if ids(parametres.get('prestations')):
        projets = projets.filter(prestation_id__in=ids(parametres['prestations']))
    if ids(parametres.get('projets')):
        projets = projets.filter(pk__in=ids(parametres['projets']))
    projets = list(projets.order_by('affaire__nom', 'prestation__nom', 'ordre', 'id'))
    statut = ids(parametres.get('statut'))
    if statut:
        suivis = resumes('projet', [p.id for p in projets])
        projets = [p for p in projets
                   if (s := suivis.get(p.id, {}).get('statut')) and s['id'] == statut[0] and not s.get('progression')]
    return projets


def analyser(user, parametres):
    """Toutes les données de la page, en une fois."""
    reglages = ParametresRendement.actuels()
    h = reglages.heures_par_jour
    granularite = 'mois' if parametres.get('granularite') == 'mois' else 'jour'
    vide = {'heures_par_jour': float(h), 'granularite': granularite, 'niveau': None, 'unite': None,
            'unites': [], 'barres': [], 'equipes': None, 'periodes': [], 'personnes': [], 'rentabilites': []}
    if not ids(parametres.get('affaires')):
        return vide   # aucune affaire cochée : rien à afficher

    niveau = ('descriptions' if ids(parametres.get('projets'))
              else 'projets' if ids(parametres.get('prestations')) else 'prestations')
    projets = projets_selectionnes(user, parametres)
    projet_de = {p.id: p for p in projets}
    unites = sorted({p.prestation.unite for p in projets})
    unite = unites[0] if len(unites) == 1 else None

    parts = (PartPointage.objects.filter(description__projet_id__in=projet_de)
             .select_related('pointage__employe', 'pointage__tache', 'description'))
    if ids(parametres.get('taches')):
        parts = parts.filter(pointage__tache_id__in=ids(parametres['taches']))
    if parametres.get('debut'):
        parts = parts.filter(pointage__date__gte=parametres['debut'])
    if parametres.get('fin'):
        parts = parts.filter(pointage__date__lte=parametres['fin'])
    parts = list(parts)
    descriptions = list(Description.objects.filter(projet_id__in=projet_de).order_by('projet__ordre', 'ordre', 'id'))

    # --- Barres : regroupement selon le niveau -------------------------------------
    def cle(description):
        projet = projet_de[description.projet_id]
        if niveau == 'prestations':
            return ('prestation', projet.prestation_id), projet.prestation.nom, projet.prestation.unite
        if niveau == 'projets':
            return ('projet', projet.id), projet.nom, projet.prestation.unite
        return ('description', description.id), f'{description.nom}', projet.prestation.unite

    barres = {}
    cle_description = {}
    for d in descriptions:
        k, nom, unite_barre = cle(d)
        cle_description[d.id] = k
        barre = barres.setdefault(k, {'cle': f'{k[0]}-{k[1]}', 'nom': nom, 'unite': unite_barre,
                                      'quantite': Decimal(0), 'minutes': 0, 'objectif_pondere': Decimal(0)})
        quantite = d.quantite or Decimal(0)
        barre['quantite'] += quantite
        barre['objectif_pondere'] += quantite * projet_de[d.projet_id].rendement.valeur
        barre.setdefault('objectifs', []).append(projet_de[d.projet_id].rendement.valeur)
    for part in parts:
        barres[cle_description[part.description_id]]['minutes'] += part.minutes_normales + part.minutes_hs

    lignes_barres = []
    for b in barres.values():
        objectif = (b['objectif_pondere'] / b['quantite']) if b['quantite'] else (sum(b['objectifs']) / len(b['objectifs']))
        lignes_barres.append({
            'cle': b['cle'], 'nom': b['nom'], 'unite': b['unite'],
            'quantite': float(b['quantite']), 'heures': round(b['minutes'] / 60, 2),
            'rendement': rendement(b['quantite'], b['minutes'], h), 'objectif': round(float(objectif), 2),
        })

    # --- Global (équipes) : seulement avec une unité commune --------------------------
    quantite_totale = sum((b['quantite'] for b in barres.values()), Decimal(0))
    minutes_totales = sum(b['minutes'] for b in barres.values())
    objectif_global = (sum((b['objectif_pondere'] for b in barres.values()), Decimal(0)) / quantite_totale
                       if quantite_totale else None)
    equipes = {
        'quantite': float(quantite_totale), 'heures': round(minutes_totales / 60, 2),
        'rendement': rendement(quantite_totale, minutes_totales, h) if unite else None,
        'objectif': round(float(objectif_global), 2) if (unite and objectif_global is not None) else None,
    }

    # --- Personnes : quantité des descriptions où elles sont « Employé » ------------
    employe_de = dict(LigneFeuille.objects.filter(description_id__in=[d.id for d in descriptions], employe__isnull=False)
                      .values_list('description_id', 'employe_id'))
    quantite_description = {d.id: d.quantite or Decimal(0) for d in descriptions}
    personnes = {}
    minutes_personne = defaultdict(int)
    minutes_personne_description = defaultdict(int)
    minutes_periode = defaultdict(int)
    minutes_periode_description = defaultdict(int)
    cle_periode = (lambda d: d.strftime('%Y-%m')) if granularite == 'mois' else (lambda d: d.isoformat())
    for part in parts:
        employe = part.pointage.employe
        personnes[employe.id] = employe
        minutes = part.minutes_normales + part.minutes_hs
        periode = cle_periode(part.pointage.date)
        minutes_personne[employe.id] += minutes
        minutes_personne_description[(employe.id, part.description_id)] += minutes
        minutes_periode[(employe.id, periode)] += minutes
        minutes_periode_description[(employe.id, part.description_id, periode)] += minutes

    quantite_personne = defaultdict(Decimal)
    for description_id, employe_id in employe_de.items():
        quantite_personne[employe_id] += quantite_description.get(description_id, Decimal(0))
    quantite_periode = defaultdict(Decimal)
    for (employe_id, description_id, periode), minutes in minutes_periode_description.items():
        if employe_de.get(description_id) != employe_id:
            continue
        total = minutes_personne_description[(employe_id, description_id)]
        if total:
            quantite_periode[(employe_id, periode)] += quantite_description[description_id] * minutes / total

    periodes = sorted({p for _, p in minutes_periode})
    lignes_personnes = []
    for employe in sorted(personnes.values(), key=lambda e: (e.nom, e.prenom)):
        lignes_personnes.append({
            'id': employe.id, 'nom_affiche': employe.nom_affiche, 'identifiant': employe.identifiant,
            'code_barre': employe.code_barre,
            'quantite': float(quantite_personne[employe.id]), 'heures': round(minutes_personne[employe.id] / 60, 2),
            # Sans unité commune, pas de rendement (on n'additionne pas des fiches et des pages)
            'rendement': rendement(quantite_personne[employe.id], minutes_personne[employe.id], h) if unite else None,
            'evolution': [rendement(quantite_periode[(employe.id, p)], minutes_periode[(employe.id, p)], h) or 0
                          for p in periodes] if unite else [],
        })

    return {
        **vide,
        'niveau': niveau, 'unite': unite, 'unites': unites,
        'barres': lignes_barres, 'equipes': equipes,
        'periodes': periodes if unite else [], 'personnes': lignes_personnes,
    }


def options(user, parametres):
    """Listes des filtres : affaires, puis prestations et projets selon les affaires / prestations cochées."""
    affaires = affaires_visibles(user).order_by('nom')
    projets = Projet.objects.filter(affaire__in=affaires).select_related('prestation', 'affaire')
    if ids(parametres.get('affaires')):
        projets = projets.filter(affaire_id__in=ids(parametres['affaires']))
    prestations = {p.prestation_id: p.prestation.nom for p in projets}
    if ids(parametres.get('prestations')):
        projets = projets.filter(prestation_id__in=ids(parametres['prestations']))
    from marches.models import Statut, Tache
    return {
        'affaires': [{'id': a.id, 'nom': f'{a.num_affaire} - {a.nom}' if a.num_affaire else a.nom} for a in affaires],
        'prestations': [{'id': i, 'nom': n} for i, n in sorted(prestations.items(), key=lambda x: x[1])],
        'projets': [{'id': p.id, 'nom': p.nom, 'affaire': p.affaire.nom} for p in projets.order_by('affaire__nom', 'ordre', 'id')],
        'taches': [{'id': t.id, 'nom': t.nom} for t in Tache.objects.order_by('ordre', 'id')],
        'statuts': [{'id': s.id, 'nom': s.nom, 'couleur': s.couleur} for s in Statut.objects.order_by('ordre', 'id')],
        **commentaires_proposes(projets),
    }


# ======================================================================
# Onglet « Globale » : par employé
# ======================================================================
def globale(user, parametres):
    """
    Rendement par employé sur la sélection.

    Descriptions retenues : celles des affaires / prestations / projets cochés (statut du projet), commencées
    dans la période (« Date de début » de leur ligne de feuille : Du… Au… et mois cochés).
    Pour un employé (Employé de la ligne) : rendement de chaque description = quantité ÷ son temps pointé
    dessus (tâches cochées) × heures par jour ; rendement de l'employé = moyenne de ces rendements ;
    objectif = moyenne des objectifs de ces descriptions. Rentabilité = rendement ÷ objectif, sans plafond
    (2 = deux fois l'objectif ; recalculée à l'écran si un objectif est modifié en aperçu).
    Camembert du temps : les tâches choisies dans Paramètres > Graphiques, toutes sinon.
    """
    reglages = ParametresRendement.actuels()
    h = reglages.heures_par_jour
    vide = {'heures_par_jour': float(h), 'unite': None, 'unites': [], 'employes': [], 'objectifs': [],
            'temps_par_tache': [], 'taches_camembert': [], 'liste_employes': [], 'mois_disponibles': []}

    projets = projets_selectionnes(user, parametres)
    projet_de = {p.id: p for p in projets}
    lignes, mois_disponibles = lignes_selection(projet_de, parametres)
    descriptions = {l.description_id: l.description for l in lignes}
    employe_de = {l.description_id: l.employe for l in lignes if l.employe_id}
    unites = sorted({projet_de[d.projet_id].prestation.unite for d in descriptions.values()})
    unite = unites[0] if len(unites) == 1 else None

    parts = temps_pointes(parametres, pk__in=list(descriptions))
    parts_temps = filtrer_taches(parts, ids(parametres.get('taches')))
    filtre_employes = set(ids(parametres.get('employes')))

    # Temps de chaque employé sur chaque description (tâches cochées)
    minutes = defaultdict(int)
    for part in parts_temps:
        minutes[(part.pointage.employe_id, part.description_id)] += part.minutes_normales + part.minutes_hs

    # Liste des employés proposés en filtre : Employés des lignes et personnes qui ont pointé
    personnes = {e.id: e for e in employe_de.values()}
    for part in parts:
        personnes.setdefault(part.pointage.employe_id, part.pointage.employe)
    liste_employes = [{'id': e.id, 'nom': e.nom_affiche, 'identifiant': e.identifiant}
                      for e in sorted(personnes.values(), key=lambda e: (e.nom, e.prenom))]

    garder = (lambda e_id: e_id in filtre_employes) if filtre_employes else (lambda e_id: True)
    employes = {}
    for description_id, employe in employe_de.items():
        if not garder(employe.id):
            continue
        d = descriptions[description_id]
        projet = projet_de[d.projet_id]
        fiche = employes.setdefault(employe.id, {
            'id': employe.id, 'nom_affiche': employe.nom_affiche, 'identifiant': employe.identifiant,
            'code_barre': employe.code_barre, 'quantite': 0.0, 'heures': 0.0, 'descriptions': [],
        })
        temps = minutes.get((employe.id, description_id), 0)
        fiche['quantite'] += float(d.quantite or 0)
        fiche['heures'] += temps / 60
        fiche['descriptions'].append({
            'id': d.id, 'nom': d.nom, 'prestation_id': projet.prestation_id, 'unite': projet.prestation.unite,
            'quantite': float(d.quantite or 0), 'heures': round(temps / 60, 2),
            'rendement': rendement(d.quantite, temps, h), 'objectif': float(projet.rendement.valeur),
        })

    lignes_employes = []
    for fiche in sorted(employes.values(), key=lambda f: f['nom_affiche']):
        mesurees = [d for d in fiche['descriptions'] if d['rendement'] is not None]
        moyenne = sum(d['rendement'] for d in mesurees) / len(mesurees) if mesurees and unite else None
        objectif = sum(d['objectif'] for d in mesurees) / len(mesurees) if mesurees else None
        fiche.update({
            'heures': round(fiche['heures'], 2),
            'rendement': moyenne, 'objectif': objectif,
            'rentabilite': moyenne / objectif if moyenne is not None and objectif else None,
        })
        lignes_employes.append(fiche)

    # Objectifs par prestation (tableau « Rendement objectif ») : moyenne pondérée par les quantités
    par_prestation = {}
    for d in descriptions.values():
        projet = projet_de[d.projet_id]
        p = par_prestation.setdefault(projet.prestation_id, {'id': projet.prestation_id, 'nom': projet.prestation.nom,
                                                             'unite': projet.prestation.unite, 'q': Decimal(0), 'pondere': Decimal(0), 'liste': []})
        p['q'] += d.quantite or 0
        p['pondere'] += (d.quantite or 0) * projet.rendement.valeur
        p['liste'].append(projet.rendement.valeur)
    objectifs = [{'id': p['id'], 'nom': p['nom'], 'unite': p['unite'],
                  'objectif': round(float(p['pondere'] / p['q'] if p['q'] else sum(p['liste']) / len(p['liste'])), 2)}
                 for p in sorted(par_prestation.values(), key=lambda p: p['nom'])]

    # Temps par tâche (camembert) : tâches de Paramètres > Graphiques (toutes sinon), employés cochés
    from .models import ParametresGraphiques
    taches_camembert = list(ParametresGraphiques.actuels().taches_camembert.order_by('ordre', 'id').values('id', 'nom'))
    parts_camembert = filtrer_taches(parts, [t['id'] for t in taches_camembert]) if taches_camembert else parts
    temps_tache = defaultdict(int)
    noms_taches = {}
    for part in parts_camembert:
        if not garder(part.pointage.employe_id):
            continue
        temps_tache[part.pointage.tache_id] += part.minutes_normales + part.minutes_hs
        noms_taches[part.pointage.tache_id] = part.pointage.tache.nom
    temps_par_tache = [{'id': t, 'nom': noms_taches[t], 'heures': round(m / 60, 2)}
                       for t, m in sorted(temps_tache.items(), key=lambda x: -x[1])]

    return {**vide, 'source': 'feuilles' if mode_feuilles(parametres) else ('pointages_seuls' if mode_pointages(parametres) else 'pointages'),
            'unite': unite, 'unites': unites, 'employes': lignes_employes, 'objectifs': objectifs,
            'temps_par_tache': temps_par_tache, 'taches_camembert': taches_camembert,
            'liste_employes': liste_employes, 'mois_disponibles': mois_disponibles}


# ======================================================================
# Onglet « Evolution » : deux courbes de rendement par date pointée
# ======================================================================
def evolution(user, parametres):
    """
    Comme Globale (sans projets / communes), plus deux courbes définies dans Paramètres > Graphiques.

    Courbe = un groupe de tâches. Pour chaque date pointée :
        rendement = Σ quantité attribuée à la date ÷ Σ temps des tâches de la courbe × heures par jour
    où la quantité d'une description est répartie sur ses dates au prorata du temps pointé avec ces tâches
    (employés cochés). Sans unité commune : pas de courbe (on ne mélange pas fiches et pages).
    """
    from .models import ParametresGraphiques

    base = {k: v for k, v in parametres.items() if k != 'projets'}
    donnees = globale(user, base)
    reglages = ParametresGraphiques.actuels()
    courbes_parametrees = [
        {'nom': reglages.courbe1_nom, 'couleur': reglages.courbe1_couleur, 'taches': list(reglages.courbe1_taches.values('id', 'nom'))},
        {'nom': reglages.courbe2_nom, 'couleur': reglages.courbe2_couleur, 'taches': list(reglages.courbe2_taches.values('id', 'nom'))},
    ]
    resultat = {**donnees, 'dates': [], 'courbes': [{**c, 'valeurs': []} for c in courbes_parametrees], 'objectif': None}
    if not donnees['unite']:
        return resultat

    h = ParametresRendement.actuels().heures_par_jour
    # Mêmes descriptions que Globale : on les retrouve par les lignes de feuille filtrées
    projets = projets_selectionnes(user, base)
    lignes, _ = lignes_selection([p.id for p in projets], parametres)
    quantite = {l.description_id: l.description.quantite or Decimal(0) for l in lignes}

    parts = dates(temps_pointes(parametres, pk__in=list(quantite)))
    if ids(parametres.get('employes')):
        parts = [p for p in parts if p.pointage.employe_id in ids(parametres['employes'])]

    dates_vues = set()
    courbes = []
    for courbe in courbes_parametrees:
        minutes = defaultdict(int)          # (description, date) -> minutes
        total_description = defaultdict(int)
        for p in filtrer_taches(parts, [t['id'] for t in courbe['taches']]):
            m = p.minutes_normales + p.minutes_hs
            minutes[(p.description_id, p.pointage.date)] += m
            total_description[p.description_id] += m
        q_date, m_date = defaultdict(Decimal), defaultdict(int)
        for (description_id, jour), m in minutes.items():
            q_date[jour] += quantite[description_id] * m / total_description[description_id]
            m_date[jour] += m
            dates_vues.add(jour)
        courbes.append((courbe, q_date, m_date))

    liste_dates = sorted(dates_vues)
    resultat['dates'] = [d.isoformat() for d in liste_dates]
    resultat['courbes'] = [{
        **courbe, 'valeurs': [rendement(q_date.get(d), m_date.get(d, 0), h) for d in liste_dates],
    } for courbe, q_date, m_date in courbes]
    objectifs = donnees['objectifs']
    resultat['objectif'] = objectifs[0]['objectif'] if len(objectifs) == 1 else None
    return resultat


# ======================================================================
# Onglet « Réel vs Objectif » : deux barres par employé
# ======================================================================
def reel_objectif(user, parametres):
    """
    Comme Globale, sans filtre de tâches. Par employé, deux barres (Paramètres > Graphiques) :
      barre 1 = le réel : rendement moyen de ses descriptions avec le temps des tâches de la barre 1 ;
      barre 2 = le Rendement objectif : moyenne des objectifs de ces descriptions (modifiable en aperçu).
    """
    from .models import ParametresGraphiques

    reglages = ParametresGraphiques.actuels()
    taches = list(reglages.barre1_taches.values('id', 'nom'))
    barres = [
        {'nom': reglages.barre1_nom, 'couleur': reglages.barre1_couleur, 'taches': taches, 'objectif': False},
        {'nom': reglages.barre2_nom, 'couleur': reglages.barre2_couleur, 'taches': [], 'objectif': True},
    ]
    base = {k: v for k, v in parametres.items() if k != 'taches'}
    donnees = globale(user, {**base, 'taches': ','.join(str(t['id']) for t in taches)})
    employes = [{
        'id': e['id'], 'identifiant': e['identifiant'], 'nom_affiche': e['nom_affiche'], 'code_barre': e['code_barre'],
        'quantite': e['quantite'], 'heures': e['heures'], 'rendement': e['rendement'], 'objectif': e['objectif'],
        'rentabilite': e['rentabilite'], 'descriptions': e['descriptions'],
    } for e in sorted(donnees['employes'], key=lambda e: e['identifiant'])]
    return {
        **{k: donnees[k] for k in ('heures_par_jour', 'unite', 'unites', 'objectifs', 'liste_employes', 'mois_disponibles', 'source')},
        'barres': barres, 'employes': employes,
    }


# ======================================================================
# Onglet « Evaluation Employé » : rendement moyen par mois
# ======================================================================
def evaluation(user, parametres):
    """
    Comme Globale (sans projets / communes). Histogramme : une barre par mois de pointage.

      rendement d'une description pour un employé = quantité ÷ son temps dessus (tâches cochées) × heures par jour
      (la quantité est partagée entre les mois au prorata de son temps : le rendement est le même chaque mois) ;
      mois = moyenne, sur les employés (cochés, tous sinon), de la moyenne des descriptions qu'ils ont pointées ce mois-là.
    Chaque employé du mois est renvoyé avec les objectifs de ses descriptions, pour l'aperçu des objectifs à l'écran.
    """
    base = {k: v for k, v in parametres.items() if k != 'projets'}
    donnees = globale(user, base)
    resultat = {**donnees, 'mois': []}
    if not donnees['unite'] and not mode_pointages(parametres):   # en heures (source « Pointages »), les unités n'importent pas
        return resultat

    h = ParametresRendement.actuels().heures_par_jour
    projets = {p.id: p for p in projets_selectionnes(user, base)}
    lignes, _ = lignes_selection(projets, parametres)
    lignes = [l for l in lignes if l.employe_id]
    filtre_employes = set(ids(parametres.get('employes')))
    employe_de = {l.description_id: l.employe for l in lignes if not filtre_employes or l.employe_id in filtre_employes}
    descriptions = {l.description_id: l.description for l in lignes}

    parts = dates(filtrer_taches(temps_pointes(parametres, pk__in=list(employe_de)), ids(parametres.get('taches'))))
    minutes_mois = defaultdict(int)       # (description, mois) -> minutes de l'Employé de la ligne
    minutes_total = defaultdict(int)
    for part in parts:
        employe = employe_de[part.description_id]
        if part.pointage.employe_id != employe.id:
            continue
        m = part.minutes_normales + part.minutes_hs
        minutes_mois[(part.description_id, part.pointage.date.strftime('%Y-%m'))] += m
        minutes_total[part.description_id] += m

    par_mois = defaultdict(lambda: defaultdict(list))   # mois -> employé -> [(rendement, prestation, objectif)]
    for (description_id, mois), m in minutes_mois.items():
        d = descriptions[description_id]
        projet = projets[d.projet_id]
        valeur = rendement(d.quantite, minutes_total[description_id], h)
        if valeur is not None:
            par_mois[mois][employe_de[description_id]].append((valeur, projet.prestation_id, float(projet.rendement.valeur)))

    heures_mois = defaultdict(int)   # heures pointées par mois (source « Pointages » : le graphique est en heures)
    for (_, mois), m in minutes_mois.items():
        heures_mois[mois] += m

    for mois in sorted(set(par_mois) | set(heures_mois)):
        employes = []
        for employe, mesures in sorted(par_mois[mois].items(), key=lambda x: x[0].identifiant):
            employes.append({
                'id': employe.id, 'identifiant': employe.identifiant,
                'rendement': sum(v for v, _, _ in mesures) / len(mesures),
                'objectifs': [{'prestation_id': p, 'objectif': o} for _, p, o in mesures],
            })
        resultat['mois'].append({
            'mois': mois, 'employes': employes, 'heures': round(heures_mois.get(mois, 0) / 60, 2),
            'rendement': sum(e['rendement'] for e in employes) / len(employes) if employes else None,
        })
    return resultat


# ======================================================================
# Onglet « Analyse » : où chaque employé passe son temps, et avec quel résultat
# ======================================================================
ZONES = {
    'garder': 'À garder', 'revoir': 'À revoir', 'potentiel': 'Potentiel', 'ponctuel': 'Ponctuel', 'aide': 'Aide',
}


def _rang_mois(mois):
    annee, numero = (int(x) for x in mois.split('-'))
    return annee * 12 + numero


def analyse_employes(user, parametres):
    """
    Pour chaque employé coché, mois par mois et par affaire / prestation :
      heures pointées (tâches cochées), part de son temps du mois, heures d'« aide » (lignes dont il n'est pas
      l'Employé), rendement moyen de ses descriptions (quantité ÷ son temps × heures par jour, quantité au prorata
      du temps), objectif, rentabilité = rendement ÷ objectif (échelle commune à toutes les unités).
    Zone (carte du mois) : beaucoup de temps (≥ seuil) / peu de temps × rentabilité ≥ 1 / < 1.
    Badges : Aide, En adaptation (premiers mois sur la prestation et rentabilité < 1),
             Baisse soudaine (chute ≥ seuil par rapport à ses mois précédents sur la prestation, alors qu'il est ≥ 1 ailleurs).
    Seuils : Paramètres > Graphiques.
    Mois analysés (?mois=2026-10,2026-11 ; aucun = tous) : la carte additionne la période (part du temps sur la
    période, rentabilité sur toutes les descriptions travaillées) ; signaux = ceux d'au moins un des mois.
    """
    from marches.models import Projet as ProjetModele

    from .models import ParametresGraphiques

    reglages = ParametresGraphiques.actuels()
    seuils = {
        'temps': reglages.analyse_seuil_temps, 'aide': reglages.analyse_seuil_aide,
        'adaptation': reglages.analyse_mois_adaptation, 'baisse': reglages.analyse_seuil_baisse,
    }
    h = ParametresRendement.actuels().heures_par_jour

    projets = ProjetModele.objects.filter(affaire__in=affaires_visibles(user)).select_related('affaire', 'prestation', 'rendement')
    if ids(parametres.get('affaires')):
        projets = projets.filter(affaire_id__in=ids(parametres['affaires']))
    if ids(parametres.get('prestations')):
        projets = projets.filter(prestation_id__in=ids(parametres['prestations']))
    projet_de = {p.id: p for p in projets}

    parts = dates(filtrer_taches(temps_pointes(parametres, projet_id__in=list(projet_de)), ids(parametres.get('taches'))))

    personnes = {}
    for part in parts:
        personnes.setdefault(part.pointage.employe_id, part.pointage.employe)
    liste_employes = [{'id': e.id, 'nom': e.nom_affiche, 'identifiant': e.identifiant}
                      for e in sorted(personnes.values(), key=lambda e: e.identifiant)]

    choisis = [i for i in ids(parametres.get('employes')) if i in personnes]
    mois_tous = sorted({part.pointage.date.strftime('%Y-%m') for part in parts if part.pointage.employe_id in choisis})
    # Mois analysés : ceux cochés (parmi les mois disponibles), tous si aucun
    mois_coches = [m for m in str(parametres.get('mois') or '').split(',') if m in mois_tous]
    periode = set(mois_coches or mois_tous)
    resultat = {'heures_par_jour': float(h), 'source': 'feuilles' if mode_feuilles(parametres) else 'pointages',
                'seuils': seuils, 'liste_employes': liste_employes,
                'mois_disponibles': list(reversed(mois_tous)), 'mois': sorted(mois_coches), 'employes': []}
    if not choisis:
        return resultat

    if mode_pointages(parametres):
        proprietaire = {l.description_id: l.employe_id for l in _lignes_des_pointages(projet_de)}
    else:
        proprietaire = dict(LigneFeuille.objects.filter(description__projet_id__in=projet_de, employe__isnull=False)
                            .values_list('description_id', 'employe_id'))

    for employe_id in choisis:
        employe = personnes[employe_id]
        siennes = [p for p in parts if p.pointage.employe_id == employe_id]
        total_description = defaultdict(int)
        for p in siennes:
            total_description[p.description_id] += p.minutes_normales + p.minutes_hs

        cases = defaultdict(lambda: {'minutes': 0, 'minutes_aide': 0, 'descriptions': set()})
        total_mois = defaultdict(int)
        libelles = {}
        for p in siennes:
            projet = projet_de[p.description.projet_id]
            cle = f'{projet.affaire_id}-{projet.prestation_id}'
            libelles[cle] = (projet.affaire, projet.prestation)
            mois = p.pointage.date.strftime('%Y-%m')
            m = p.minutes_normales + p.minutes_hs
            case = cases[(cle, mois)]
            case['minutes'] += m
            total_mois[mois] += m
            if proprietaire.get(p.description_id) == employe_id:
                case['descriptions'].add(p.description_id)
            else:
                case['minutes_aide'] += m

        descriptions = {d.id: d for d in Description.objects.filter(pk__in={d for c in cases.values() for d in c['descriptions']})}
        calcul = {}
        for (cle, mois), case in cases.items():
            mesures = []
            for description_id in case['descriptions']:
                d = descriptions[description_id]
                valeur = rendement(d.quantite, total_description[description_id], h)
                if valeur is not None:
                    mesures.append((valeur, float(projet_de[d.projet_id].rendement.valeur)))
            r = sum(v for v, _ in mesures) / len(mesures) if mesures else None
            o = sum(o for _, o in mesures) / len(mesures) if mesures else None
            calcul[(cle, mois)] = {
                'minutes': case['minutes'], 'minutes_aide': case['minutes_aide'], 'descriptions': case['descriptions'],
                'heures': round(case['minutes'] / 60, 2), 'heures_aide': round(case['minutes_aide'] / 60, 2),
                'part': case['minutes'] / total_mois[mois] if total_mois[mois] else 0,
                'rendement': r, 'objectif': o, 'rentabilite': r / o if r is not None and o else None,
            }

        premier_mois = {}
        for (cle, mois) in calcul:
            if cle not in premier_mois or mois < premier_mois[cle]:
                premier_mois[cle] = mois

        for (cle, mois), c in calcul.items():
            badges = []
            aide = c['heures'] and c['heures_aide'] / c['heures'] * 100 >= seuils['aide']
            if aide:
                badges.append({'code': 'aide', 'libelle': 'Aide'})
            if c['rentabilite'] is not None:
                if c['rentabilite'] < 1 and _rang_mois(mois) - _rang_mois(premier_mois[cle]) < seuils['adaptation']:
                    badges.append({'code': 'adaptation', 'libelle': 'En adaptation'})
                precedents = [calcul[(cle, m)]['rentabilite'] for m in sorted({m for (k, m) in calcul if k == cle and m < mois})
                              if calcul[(cle, m)]['rentabilite'] is not None]
                ailleurs = [x['rentabilite'] for (k, m), x in calcul.items() if m == mois and k != cle and x['rentabilite'] is not None]
                if (precedents and c['rentabilite'] <= (sum(precedents) / len(precedents)) * (1 - seuils['baisse'] / 100)
                        and any(x >= 1 for x in ailleurs)):
                    badges.append({'code': 'baisse', 'libelle': 'Baisse soudaine'})
                beaucoup = c['part'] * 100 >= seuils['temps']
                zone = ('garder' if c['rentabilite'] >= 1 else 'revoir') if beaucoup else ('potentiel' if c['rentabilite'] >= 1 else 'ponctuel')
            else:
                zone = 'aide' if aide else None
            c.update({'badges': badges, 'zone': zone, 'zone_libelle': ZONES.get(zone, '—')})

        def zone_de(part, rentabilite, aide):
            if rentabilite is None:
                return 'aide' if aide else None
            if part * 100 >= seuils['temps']:
                return 'garder' if rentabilite >= 1 else 'revoir'
            return 'potentiel' if rentabilite >= 1 else 'ponctuel'

        # Carte de la période : addition des mois analysés
        total_periode = sum(total_mois.get(m, 0) for m in periode)
        carte_par_cle = {}
        for (cle, mois), c in calcul.items():
            if mois not in periode:
                continue
            a = carte_par_cle.setdefault(cle, {'minutes': 0, 'minutes_aide': 0, 'descriptions': set(), 'badges': {}})
            a['minutes'] += c['minutes']
            a['minutes_aide'] += c['minutes_aide']
            a['descriptions'] |= c['descriptions']
            for b in c['badges']:
                a['badges'].setdefault(b['code'], {**b, 'mois': []})['mois'].append(mois)

        mois_employe = sorted({m for (_, m) in calcul})[-12:]
        lignes_suivi = []
        for cle, (affaire, prestation) in sorted(libelles.items(), key=lambda x: (x[1][0].nom, x[1][1].nom)):
            lignes_suivi.append({
                'cle': cle, 'affaire': f'{affaire.num_affaire} - {affaire.nom}' if affaire.num_affaire else affaire.nom,
                'prestation': prestation.nom, 'unite': prestation.unite,
                'cases': {m: calcul[(cle, m)] for m in mois_employe if (cle, m) in calcul},
            })
        carte = []
        for l in lignes_suivi:
            a = carte_par_cle.get(l['cle'])
            if not a:
                continue
            mesures = []
            for description_id in a['descriptions']:
                d = descriptions[description_id]
                valeur = rendement(d.quantite, total_description[description_id], h)
                if valeur is not None:
                    mesures.append((valeur, float(projet_de[d.projet_id].rendement.valeur)))
            r = sum(v for v, _ in mesures) / len(mesures) if mesures else None
            o = sum(o for _, o in mesures) / len(mesures) if mesures else None
            rentabilite = r / o if r is not None and o else None
            part = a['minutes'] / total_periode if total_periode else 0
            aide = a['minutes'] and a['minutes_aide'] / a['minutes'] * 100 >= seuils['aide']
            zone = zone_de(part, rentabilite, aide)
            carte.append({
                'cle': l['cle'], 'affaire': l['affaire'], 'prestation': l['prestation'], 'unite': l['unite'],
                'heures': round(a['minutes'] / 60, 2), 'heures_aide': round(a['minutes_aide'] / 60, 2), 'part': part,
                'rendement': r, 'objectif': o, 'rentabilite': rentabilite, 'zone': zone, 'zone_libelle': ZONES.get(zone, '—'),
                'badges': sorted(a['badges'].values(), key=lambda b: b['code']),
            })
        carte.sort(key=lambda x: -x['heures'])
        for c in calcul.values():
            for cle_interne in ('minutes', 'minutes_aide', 'descriptions'):
                c.pop(cle_interne, None)
        resultat['employes'].append({
            'id': employe.id, 'identifiant': employe.identifiant, 'nom_affiche': employe.nom_affiche,
            'code_barre': employe.code_barre,
            'heures_mois': round(total_periode / 60, 2),
            'carte': carte,
            'suivi': {'mois': mois_employe, 'lignes': lignes_suivi},
        })
    return resultat
