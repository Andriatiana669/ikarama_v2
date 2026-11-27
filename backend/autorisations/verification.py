# backend/autorisations/verification.py
"""
Paramètres > Vérification des droits (superadmin) :
  fiche(employe)       ses postes et pôles, son accès au site, ses rôles appliqués (et comment), les rôles visés
                       par un intitulé proche mais pas reconnu, et la grille complète module × action avec les raisons ;
  comparer(a, b)       les deux grilles côte à côte, seulement les différences mises en évidence ;
  anomalies()          ce qui empêche le plus souvent un rôle de s'appliquer comme prévu.
"""
import difflib
from collections import defaultdict
from types import SimpleNamespace

from utilisateurs.models import Employe, EmployePoste
from utilisateurs.serializers import EmployeResumeSerializer

from . import acces
from .droits import ACTIONS, MODULES, PERIMETRES_TOTAUX, _regles, expliquer, roles_de
from .intitules import normaliser
from .models import AttributionRole, DroitRole, Role


def _utilisateur(employe):
    """Le compte de la personne, ou un compte fictif sans privilège si elle ne s'est jamais connectée."""
    user = getattr(employe, 'user', None)
    if user is not None:
        return user
    return SimpleNamespace(is_authenticated=True, is_superuser=False, is_staff=False, employe=employe)


def _comment(attribution, employe_postes):
    if attribution.critere == 'MATRICULE':
        return 'attribué à la personne'
    valeur = attribution.poste if attribution.critere == 'POSTE' else attribution.pole
    champ = 0 if attribution.critere == 'POSTE' else 1
    exact = any((p[champ] or '') == valeur for p in employe_postes)
    quoi = 'poste' if attribution.critere == 'POSTE' else 'pôle'
    texte = f'par son {quoi} « {valeur} »'
    if not exact:
        reel = next((p[champ] for p in employe_postes if normaliser(p[champ]) == normaliser(valeur)), '')
        texte += f' (écrit « {reel} » dans sa fiche RH : reconnu malgré la différence)'
    return texte


def grille(employe):
    user = _utilisateur(employe)
    lignes = []
    for code, module in MODULES.items():
        actions = []
        for action in module['actions']:
            reponse = expliquer(user, code, action)
            refuse = False
            if not reponse['autorise'] and getattr(user, 'employe', None) is not None:
                _, refus = _regles(employe, code, action)
                refuse = any(r[0] in PERIMETRES_TOTAUX for r in refus)
            actions.append({'action': action, 'libelle': ACTIONS[action], 'autorise': reponse['autorise'],
                            'refuse': refuse, 'resume': reponse['resume'], 'raisons': reponse['raisons']})
        lignes.append({'module': code, 'libelle': module['libelle'], 'actions': actions})
    return lignes


def fiche(employe):
    user = _utilisateur(employe)
    postes = list(employe.postes.values_list('poste_nom', 'pole'))
    roles = roles_de(employe)
    attributions = (AttributionRole.objects.filter(role__in=roles, actif=True).select_related('role')
                    .order_by('role__nom'))
    appliques = defaultdict(list)
    for a in attributions:
        if (a.critere == 'MATRICULE' and a.employe_id == employe.pk) or (
                a.critere == 'POSTE' and normaliser(a.poste) in {normaliser(p) for p, _ in postes if p}) or (
                a.critere == 'POLE' and normaliser(a.pole) in {normaliser(p) for _, p in postes if p}):
            appliques[a.role_id].append(_comment(a, postes))
    # Rôles visés par un intitulé proche (faute de frappe, mot en plus…) mais qui ne s'appliquent pas
    proches = []
    intitules = {'POSTE': [p for p, _ in postes if p], 'POLE': [p for _, p in postes if p]}
    for a in AttributionRole.objects.filter(actif=True, critere__in=['POSTE', 'POLE']).exclude(role__in=roles).select_related('role'):
        valeur = a.poste if a.critere == 'POSTE' else a.pole
        candidats = [normaliser(v) for v in intitules[a.critere]]
        if difflib.get_close_matches(normaliser(valeur), candidats, n=1, cutoff=0.8):
            proches.append({'role': a.role.nom, 'critere': 'poste' if a.critere == 'POSTE' else 'pôle', 'valeur': valeur,
                            'fiche': ', '.join(intitules[a.critere])})
    acces_site = acces.expliquer(employe)
    return {
        'employe': EmployeResumeSerializer(employe).data,
        'superadmin': bool(getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False)),
        'jamais_connecte': getattr(employe, 'user', None) is None,
        'postes': [{'poste': p or '', 'pole': pl or ''} for p, pl in postes],
        'acces_site': acces_site,
        'roles': [{'id': r.id, 'nom': r.nom, 'comment': appliques.get(r.id, [])} for r in sorted(roles, key=lambda r: r.nom)],
        'roles_proches': proches,
        'grille': grille(employe),
    }


def comparer(a, b):
    fa, fb = fiche(a), fiche(b)
    differences = 0
    lignes = []
    for ma, mb in zip(fa['grille'], fb['grille']):
        actions = []
        for xa, xb in zip(ma['actions'], mb['actions']):
            diff = xa['autorise'] != xb['autorise']
            differences += diff
            actions.append({'action': xa['action'], 'libelle': xa['libelle'], 'difference': diff, 'a': xa, 'b': xb})
        lignes.append({'module': ma['module'], 'libelle': ma['libelle'], 'actions': actions,
                       'differences': sum(1 for x in actions if x['difference'])})
    return {'a': {k: fa[k] for k in fa if k != 'grille'}, 'b': {k: fb[k] for k in fb if k != 'grille'},
            'differences': differences, 'grille': lignes}


def anomalies():
    resultat = []
    # Intitulés connus (fiches RH)
    postes = list(EmployePoste.objects.values_list('employe_id', 'poste_nom', 'pole'))
    connus = {'POSTE': defaultdict(set), 'POLE': defaultdict(set)}
    for _, poste, pole in postes:
        if poste:
            connus['POSTE'][normaliser(poste)].add(poste)
        if pole:
            connus['POLE'][normaliser(pole)].add(pole)

    # 1. Attributions par poste / pôle qui ne correspondent à personne
    elements = []
    for a in AttributionRole.objects.filter(actif=True, critere__in=['POSTE', 'POLE']).select_related('role'):
        valeur = a.poste if a.critere == 'POSTE' else a.pole
        if normaliser(valeur) not in connus[a.critere]:
            proches = difflib.get_close_matches(normaliser(valeur), list(connus[a.critere]), n=3, cutoff=0.6)
            suggestions = sorted({v for n in proches for v in connus[a.critere][n]})
            elements.append({'texte': f"Rôle « {a.role.nom} » attribué au {'poste' if a.critere == 'POSTE' else 'pôle'} « {valeur} »",
                             'detail': f"Aucune fiche RH n'a cet intitulé{(' : vouliez-vous dire ' + ', '.join(f'« {s} »' for s in suggestions) + ' ?') if suggestions else '.'}"})
    resultat.append({'code': 'attribution_sans_personne', 'gravite': 'erreur',
                     'titre': 'Attributions qui ne correspondent à personne', 'elements': elements,
                     'aide': 'Le rôle ne s’applique à personne : corrigez l’intitulé dans « Qui a ce rôle ».'})

    # 2. Intitulés écrits de plusieurs façons dans les fiches RH (reconnus comme identiques, mais à harmoniser)
    elements = []
    for critere, nom in (('POSTE', 'Poste'), ('POLE', 'Pôle')):
        for variantes in connus[critere].values():
            if len(variantes) > 1:
                elements.append({'texte': f"{nom} écrit de {len(variantes)} façons", 'detail': ' / '.join(f'« {v} »' for v in sorted(variantes))})
    resultat.append({'code': 'intitules_variantes', 'gravite': 'info',
                     'titre': 'Intitulés écrits de plusieurs façons (fiches RH)', 'elements': elements,
                     'aide': 'Ikarama les reconnaît comme identiques ; à harmoniser dans l’API RH pour plus de clarté.'})

    # 3. Rôles désactivés qui ont encore des attributions ; rôles sans droit ; rôles attribués à personne
    elements = []
    for r in Role.objects.all().order_by('nom'):
        nb_attributions = r.attributions.filter(actif=True).count()
        nb_droits = r.droits.count()
        if not r.actif and nb_attributions:
            elements.append({'texte': f"Rôle « {r.nom} » désactivé", 'detail': f'{nb_attributions} attribution(s) active(s) sans effet.'})
        elif r.actif and not nb_droits:
            elements.append({'texte': f"Rôle « {r.nom} » sans aucun droit", 'detail': 'Il ne change rien pour les personnes qui l’ont.'})
        elif r.actif and not nb_attributions:
            elements.append({'texte': f"Rôle « {r.nom} » attribué à personne", 'detail': 'Ajoutez une personne, un poste ou un pôle dans « Qui a ce rôle ».'})
    resultat.append({'code': 'roles_sans_effet', 'gravite': 'attention', 'titre': 'Rôles sans effet', 'elements': elements,
                     'aide': 'Un rôle n’agit que s’il est actif, qu’il a des droits et qu’il est attribué.'})

    # 4 et 5. Refus qui annulent un droit d'un autre rôle ; personnes ayant accès au site sans aucun rôle
    refus_totaux = defaultdict(set)   # (module, action) -> rôles qui refusent sur « Tout »
    for d in DroitRole.objects.filter(effet='REFUSER', perimetre__in=list(PERIMETRES_TOTAUX)).select_related('role'):
        refus_totaux[(d.module, d.action)].add(d.role)
    autorisations = defaultdict(set)
    for d in DroitRole.objects.filter(effet='AUTORISER').select_related('role'):
        autorisations[(d.module, d.action)].add(d.role)
    conflits = defaultdict(set)
    sans_role = []
    for e in Employe.objects.filter(acces.q_acces()).select_related('user').order_by('nom', 'prenom'):
        compte = getattr(e, 'user', None)
        if compte is not None and (compte.is_superuser or compte.is_staff):
            continue   # superadmin : tous les droits, sans rôle
        roles = set(roles_de(e))
        if not roles:
            sans_role.append(e.identifiant)
            continue
        for cle, refusants in refus_totaux.items():
            r_refus = roles & refusants
            r_auto = roles & autorisations.get(cle, set())
            if r_refus and r_auto:
                conflits[(cle, frozenset(r.nom for r in r_refus), frozenset(r.nom for r in r_auto))].add(e.identifiant)
    elements = [{'texte': f"{MODULES.get(m, {}).get('libelle', m)} > {ACTIONS.get(a, a)} : refusé par {', '.join(sorted(rf))}",
                 'detail': f"Annule l'autorisation de {', '.join(sorted(ra))} pour {len(p)} personne(s) : {', '.join(sorted(p)[:8])}{'…' if len(p) > 8 else ''}"}
                for ((m, a), rf, ra), p in sorted(conflits.items(), key=lambda x: (x[0][0], sorted(x[0][1])))]
    resultat.append({'code': 'refus_annulant', 'gravite': 'attention', 'titre': 'Refus qui annulent un droit donné par un autre rôle',
                     'elements': elements, 'aide': 'Un refus l’emporte toujours : vérifiez que c’est voulu.'})
    resultat.append({'code': 'sans_role', 'gravite': 'info', 'titre': 'Personnes ayant accès au site sans aucun rôle',
                     'elements': [{'texte': f'{len(sans_role)} personne(s)', 'detail': ', '.join(sans_role[:30]) + ('…' if len(sans_role) > 30 else '')}] if sans_role else [],
                     'aide': 'Elles n’ont que les droits de base (voir les feuilles de leurs affaires, Mes marchés, leur Planning et leur Everwin).'})
    for c in resultat:
        c['nombre'] = len(c['elements'])
    return resultat
