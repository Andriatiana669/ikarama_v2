# backend/autorisations/droits.py
"""
Moteur de décision de Paramètres > Autorisation (le « moindre privilège »).

    Décision = (droits de base + droits AUTORISER des rôles) − droits REFUSER des rôles
    Un refus l'emporte toujours. Le superadmin a tous les droits (il reste soumis à l'Accès au site).

  peut(user, module, action)                 a-t-il ce droit, au moins sur une partie ?
  q_droit(user, module, action, prefixe)     filtre Django des objets concernés (personnes ou affaires)
  peut_sur(user, module, action, objet)      ce droit sur cet objet précis (une personne, une affaire)
  verifier(user, module, action, objet)      lève une erreur 403 claire sinon
  expliquer(user, module, action, objet)     pourquoi (outil « Tester un accès »)
  droits_de(user)                            {module: [actions]} pour l'écran (menu, boutons)
"""
from django.db.models import Q

from .permissions import est_administrateur

# ----------------------------------------------------------------------
# Catalogue : modules, actions possibles, nature des objets (périmètres)
# ----------------------------------------------------------------------
ACTIONS = {
    'voir': 'Voir', 'creer': 'Créer', 'modifier': 'Modifier', 'supprimer': 'Supprimer',
    'importer': 'Importer', 'exporter': 'Exporter', 'archiver': 'Archiver', 'desarchiver': 'Désarchiver',
}
MODULES = {
    'pointages_suivi': {'libelle': 'Pointages > Suivi', 'cible': 'personnes',
                        'actions': ['voir', 'modifier', 'supprimer', 'importer', 'exporter'],
                        'aide': 'Les pointages des autres personnes (Suivi, et l’import « pour d’autres » avec la colonne Matricule).'},
    'pointages_verification': {'libelle': 'Pointages > Vérification', 'cible': 'personnes',
                               'actions': ['voir', 'exporter'],
                               'aide': 'Les jours pointés et les manques des personnes du périmètre (Vérification, et « Mon équipe » de l’Accueil).'},
    'parametres_controles': {'libelle': 'Paramètres > Contrôles de cohérence', 'cible': None,
                             'actions': ['voir'],
                             'aide': 'La page des Contrôles de cohérence (et son bloc sur l’Accueil). Le reste de Paramètres reste au superadmin.'},
    'planning_projet': {'libelle': 'Planning Projet', 'cible': 'personnes',
                        'actions': ['voir', 'creer', 'modifier', 'supprimer', 'exporter'],
                        'aide': 'Le planning des personnes du périmètre. Créer / Modifier / Supprimer = planifier, '
                                'déplacer, retirer un projet sur leurs jours à venir.'},
    'affichage_everwin': {'libelle': 'Affichage Everwin', 'cible': 'personnes',
                          'actions': ['voir', 'exporter'],
                          'aide': 'La grille Everwin des personnes du périmètre (par défaut : la sienne seulement).'},
    'gsheets_feuilles': {'libelle': 'Google Sheet > Mes feuilles', 'cible': 'affaires',
                         'actions': ['voir', 'creer', 'modifier', 'supprimer', 'importer', 'exporter'],
                         'aide': 'Les feuilles elles-mêmes (créer, modifier, supprimer, importer des feuilles, exporter la liste). '
                                 '« Créer » donne la page « Créer une nouvelle feuille ». Les données d’une feuille (ses lignes) '
                                 'suivent les règles métier : membres et responsables saisissent, le responsable importe.'},
    'marches_affaires': {'libelle': 'Marchés > Affaires', 'cible': 'affaires',
                         'actions': ['voir', 'creer', 'modifier', 'importer', 'exporter', 'archiver'],
                         'aide': 'Le panneau « Affaires » d’Ajouter un marché (la page s’affiche avec « Voir »). '
                                 '« Modifier » couvre aussi les prestations cochées pour l’affaire. '
                                 'Mes marchés reste en consultation pour les responsables et membres.'},
    'marches_prestations': {'libelle': 'Marchés > Prestations', 'cible': None,
                            'actions': ['voir', 'creer', 'modifier', 'supprimer', 'importer', 'exporter'],
                            'aide': 'Le catalogue des prestations et de leurs rendements objectifs (commun à toutes les affaires).'},
    'marches_projets': {'libelle': 'Marchés > Projets / Communes', 'cible': 'affaires',
                        'actions': ['voir', 'creer', 'modifier', 'supprimer', 'exporter'],
                        'aide': 'Les projets / communes des affaires du périmètre.'},
    'marches_descriptions': {'libelle': 'Marchés > Descriptions', 'cible': 'affaires',
                             'actions': ['voir', 'creer', 'modifier', 'supprimer', 'exporter'],
                             'aide': 'Les descriptions (et leurs quantités) des affaires du périmètre.'},
    'marches_taches': {'libelle': 'Marchés > Tâches', 'cible': None,
                       'actions': ['voir', 'creer', 'modifier', 'supprimer', 'exporter'],
                       'aide': 'Le catalogue des tâches (le formulaire de pointage garde toujours sa liste de tâches).'},
    'marches_statuts': {'libelle': 'Marchés > Statuts', 'cible': None,
                        'actions': ['voir', 'creer', 'modifier', 'supprimer', 'exporter'],
                        'aide': 'Le catalogue des statuts (les feuilles gardent toujours leur liste de statuts).'},
    'marches_duree': {'libelle': 'Marchés > Durée estimatif', 'cible': 'affaires',
                      'actions': ['voir', 'exporter'],
                      'aide': 'La page Durée estimatif, pour les projets / communes des affaires du périmètre.'},
    'marches_archives': {'libelle': 'Marchés > Archives', 'cible': 'affaires',
                         'actions': ['voir', 'supprimer', 'exporter', 'desarchiver'],
                         'aide': 'Les affaires archivées. « Supprimer » = suppression définitive.'},
}
PERIMETRES = {
    'personnes': {
        'TOUS': 'Tout le monde', 'POLE': 'Un pôle (vide : le mien)', 'POSTE': 'Un poste', 'PERSONNE': 'Une personne',
        'HIERARCHIE': 'Ma hiérarchie (tous mes subordonnés)', 'DIRECT': 'Mes collaborateurs directs (N-1)',
        'EQUIPE_DE': 'Équipe de… (une personne et toute sa hiérarchie)',
        'MEMBRES_AFFAIRES': 'Les membres de mes affaires (responsable)', 'MOI': 'Moi seulement',
    },
    'affaires': {
        'TOUTES': 'Toutes les affaires', 'RESPONSABLE': 'Mes affaires (responsable)',
        'MEMBRE': 'Mes affaires (responsable ou membre)', 'AFFAIRE': 'Une affaire précise',
        'EQUIPE_DE': 'Affaires de l’équipe de… (responsable ou membre : une personne et sa hiérarchie)',
    },
    None: {'TOUS': 'Tout'},
}
PERIMETRES_TOTAUX = {'TOUS', 'TOUTES'}


# ----------------------------------------------------------------------
# Droits de base (sans rôle) : fonction(employé) -> périmètre ou None
# ----------------------------------------------------------------------
def est_responsable(employe):
    """Responsable d'au moins une affaire en cours (mémorisé sur l'objet pour la requête)."""
    if employe is None:
        return False
    if not hasattr(employe, '_est_responsable'):
        from marches.models import Affaire
        employe._est_responsable = Affaire.objects.filter(actif=True, responsables=employe).exists()
    return employe._est_responsable


# (condition, périmètre) : condition « TOUS » (tout le monde) ou « RESPONSABLE » (responsable d'une affaire en cours)
TOUS, RESPONSABLE = 'TOUS', 'RESPONSABLE'
BASE = {
    # Seul droit de base : chacun voit les feuilles de ses affaires. Tout le reste passe par un rôle.
    'gsheets_feuilles': {'voir': (TOUS, 'MEMBRE')},
    # Planning Projet : chacun voit (et exporte) son propre planning ; planifier passe par un rôle
    'planning_projet': {'voir': (TOUS, 'MOI'), 'exporter': (TOUS, 'MOI')},
    # Affichage Everwin : chacun voit (et exporte) son propre affichage
    'affichage_everwin': {'voir': (TOUS, 'MOI'), 'exporter': (TOUS, 'MOI')},
}
LIBELLE_BASE = {
    'gsheets_feuilles': 'Tout le monde voit les feuilles de ses affaires ; le reste seulement par un rôle',
    'affichage_everwin': 'Tout le monde voit et exporte son propre affichage ; celui des autres seulement par un rôle',
    'planning_projet': 'Tout le monde voit et exporte son propre planning ; celui des autres et la planification par un rôle',
}


def perimetre_de_base(employe, module, action):
    """Périmètre du droit de base pour cette personne, ou None."""
    regle = BASE.get(module, {}).get(action)
    if regle is None:
        return None
    condition, perimetre = regle
    return perimetre if condition == TOUS or est_responsable(employe) else None


def base_de(module, action):
    """Droit de base d'une case de la grille (pour l'écran)."""
    regle = BASE.get(module, {}).get(action)
    if regle is None:
        return None
    condition, perimetre = regle
    return {'condition': 'Tout le monde' if condition == TOUS else 'Responsable d’une affaire',
            'perimetre': perimetre, 'libelle': PERIMETRES[MODULES[module]['cible']].get(perimetre, perimetre)}


# ----------------------------------------------------------------------
# Rôles de la personne (par elle-même, son poste ou son pôle)
# ----------------------------------------------------------------------
def roles_de(employe):
    if employe is None:
        return []
    if not hasattr(employe, '_roles'):
        from .models import AttributionRole
        postes = list(employe.postes.values_list('poste_nom', 'pole'))
        noms_postes = [p.lower() for p, _ in postes if p]
        poles = [p.lower() for _, p in postes if p]
        attributions = (AttributionRole.objects.filter(actif=True, role__actif=True)
                        .filter(Q(critere='MATRICULE', employe=employe) | Q(critere='POSTE') | Q(critere='POLE'))
                        .select_related('role'))
        roles = {}
        for a in attributions:
            if (a.critere == 'MATRICULE' or (a.critere == 'POSTE' and a.poste.lower() in noms_postes)
                    or (a.critere == 'POLE' and a.pole.lower() in poles)):
                roles[a.role_id] = a.role
        employe._roles = list(roles.values())
    return employe._roles


def _regles(employe, module, action):
    """(autorisations, refus) : listes de (périmètre, valeur, employe_id, affaire_id, source)."""
    autorisations, refus = [], []
    if perimetre := perimetre_de_base(employe, module, action):
        autorisations.append((perimetre, '', None, None, 'Droit de base'))
    roles = roles_de(employe)
    if roles:
        from .models import DroitRole
        for d in DroitRole.objects.filter(role__in=roles, module=module, action=action).select_related('role', 'employe', 'affaire'):
            detail = d.valeur or (d.employe.identifiant if d.employe else '') or (d.affaire.nom if d.affaire else '')
            ligne = (d.perimetre, detail, d.employe_id, d.affaire_id, f'Rôle « {d.role.nom} »')
            (refus if d.effet == 'REFUSER' else autorisations).append(ligne)
    return autorisations, refus


# ----------------------------------------------------------------------
# Périmètres -> filtres Django
# « Tout » s'écrit pk__isnull=False et non Q() : un Q() vide disparaît quand on le combine avec | ou &.
# ----------------------------------------------------------------------
def _tout(p):
    return Q(**{f'{p}pk__isnull': False})


def _q_personnes(perimetre, valeur, employe_id, employe, p):
    if perimetre == 'TOUS':
        return _tout(p)
    if perimetre == 'MOI':
        return Q(**{f'{p}pk': employe.pk})
    if perimetre == 'POLE':
        poles = [valeur] if valeur else list(employe.postes.exclude(pole='').values_list('pole', flat=True))
        q = Q(**{f'{p}pk__in': []})
        for pole in poles:
            q |= Q(**{f'{p}postes__pole__iexact': pole})
        return q
    if perimetre == 'POSTE':
        return Q(**{f'{p}postes__poste_nom__iexact': valeur})
    if perimetre == 'PERSONNE':
        return Q(**{f'{p}pk': employe_id})
    if perimetre == 'DIRECT':
        return Q(**{f'{p}chef_id': employe.pk})
    if perimetre == 'HIERARCHIE':
        return Q(**{f'{p}pk__in': [e.pk for e in employe.subordonnes_hierarchie()]})
    if perimetre == 'EQUIPE_DE':
        return Q(**{f'{p}pk__in': equipe_de(employe_id)})
    if perimetre == 'MEMBRES_AFFAIRES':
        from marches.models import Affaire
        mes_affaires = Affaire.objects.filter(actif=True, responsables=employe)
        return Q(**{f'{p}affaires_membre__in': mes_affaires}) | Q(**{f'{p}affaires_responsable__in': mes_affaires})
    return Q(**{f'{p}pk__in': []})


def equipe_de(employe_id):
    """La personne et toute sa hiérarchie (tous ses subordonnés, à tous les niveaux)."""
    from utilisateurs.models import Employe
    chef = Employe.objects.filter(pk=employe_id).first()
    return [chef.pk, *[e.pk for e in chef.subordonnes_hierarchie()]] if chef else []


def _q_affaires(perimetre, affaire_id, employe, p, employe_id=None):
    if perimetre == 'TOUTES':
        return _tout(p)
    if perimetre == 'RESPONSABLE':
        return Q(**{f'{p}responsables': employe})
    if perimetre == 'MEMBRE':
        return Q(**{f'{p}responsables': employe}) | Q(**{f'{p}membres': employe})
    if perimetre == 'AFFAIRE':
        return Q(**{f'{p}pk': affaire_id})
    if perimetre == 'EQUIPE_DE':
        equipe = equipe_de(employe_id)
        return Q(**{f'{p}responsables__in': equipe}) | Q(**{f'{p}membres__in': equipe})
    return Q(**{f'{p}pk__in': []})


def _q(regle, employe, cible, prefixe):
    perimetre, valeur, employe_id, affaire_id, _ = regle
    if cible == 'personnes':
        return _q_personnes(perimetre, valeur if perimetre in ('POLE', 'POSTE') else '', employe_id, employe, prefixe)
    if cible == 'affaires':
        return _q_affaires(perimetre, affaire_id, employe, prefixe, employe_id)
    return _tout(prefixe)


# ----------------------------------------------------------------------
# API du moteur
# ----------------------------------------------------------------------
def peut(user, module, action):
    """A-t-il ce droit, au moins sur une partie du périmètre ?"""
    if not (user and user.is_authenticated):
        return False
    if est_administrateur(user):
        return True
    employe = getattr(user, 'employe', None)
    if employe is None:
        return False
    autorisations, refus = _regles(employe, module, action)
    return bool(autorisations) and not any(r[0] in PERIMETRES_TOTAUX for r in refus)


def q_droit(user, module, action, prefixe=''):
    """Filtre des objets (personnes ou affaires, selon le module) sur lesquels l'action est permise."""
    if est_administrateur(user):
        return _tout(prefixe)
    employe = getattr(user, 'employe', None)
    rien = Q(**{f'{prefixe}pk__in': []})
    if employe is None:
        return rien
    cible = MODULES[module]['cible']
    autorisations, refus = _regles(employe, module, action)
    if not autorisations or any(r[0] in PERIMETRES_TOTAUX for r in refus):
        return rien
    permis = Q(**{f'{prefixe}pk__in': []})
    for regle in autorisations:
        permis |= _q(regle, employe, cible, prefixe)
    for regle in refus:
        permis &= ~_q(regle, employe, cible, prefixe)
    return permis


def peut_sur(user, module, action, objet):
    """Le droit sur un objet précis : une personne (Employe) ou une affaire (Affaire)."""
    if est_administrateur(user):
        return True
    if objet is None or not peut(user, module, action):
        return False
    return type(objet).objects.filter(pk=objet.pk).filter(q_droit(user, module, action)).exists()


def verifier(user, module, action, objet=None):
    """Lève une erreur 403 claire si l'action n'est pas permise (sur l'objet, s'il est donné)."""
    from .permissions import DroitManquant
    ok = peut_sur(user, module, action, objet) if objet is not None else peut(user, module, action)
    if not ok:
        hors = ' sur cet élément' if objet is not None and peut(user, module, action) else ''
        raise DroitManquant(f"Vous n’avez pas le droit « {ACTIONS.get(action, action)} » sur {MODULES[module]['libelle']}{hors}.")


def droits_de(user):
    """{module: [actions permises]} pour l'écran."""
    return {m: [a for a in infos['actions'] if peut(user, m, a)] for m, infos in MODULES.items()}


def expliquer(user, module, action, objet=None):
    """Outil « Tester un accès » : la réponse et ses raisons."""
    employe = getattr(user, 'employe', None)
    libelle = f"« {ACTIONS[action]} » sur {MODULES[module]['libelle']}"
    if est_administrateur(user):
        return {'autorise': True, 'resume': f'Oui : superadmin (tous les droits).', 'raisons': ['Superadmin : tous les droits']}
    if employe is None:
        return {'autorise': False, 'resume': 'Non : compte sans fiche employé.', 'raisons': []}
    autorisations, refus = _regles(employe, module, action)
    noms = PERIMETRES[MODULES[module]['cible']]

    def texte(r, effet):
        return f"{effet} par {r[4]} : {noms.get(r[0], r[0])}{f' ({r[1]})' if r[1] else ''}"
    raisons = [texte(r, 'Autorisé') for r in autorisations] + [texte(r, 'Refusé') for r in refus]
    if not autorisations:
        base = LIBELLE_BASE.get(module, '')
        return {'autorise': False, 'resume': f'Non : aucun droit {libelle}.', 'raisons': raisons or [f'Droit de base : {base}']}
    if any(r[0] in PERIMETRES_TOTAUX for r in refus):
        return {'autorise': False, 'resume': f'Non : refusé par un rôle ({libelle}).', 'raisons': raisons}
    if objet is not None and MODULES[module]['cible']:
        ok = peut_sur(user, module, action, objet)
        return {'autorise': ok, 'resume': f"{'Oui' if ok else 'Non'} pour « {objet} » : {'dans' if ok else 'hors de'} son périmètre.",
                'raisons': raisons}
    return {'autorise': True, 'resume': f'Oui, sur son périmètre ({libelle}).', 'raisons': raisons}
