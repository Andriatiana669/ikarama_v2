# backend/ikarama/controles.py
"""
Contrôles de cohérence (Paramètres > Contrôles de cohérence, administrateurs) : chaque contrôle compte les
problèmes trouvés et liste les premiers, avec un lien vers la page où les corriger.
  GET /api/controles/            tous les contrôles (nombre + 50 premiers éléments chacun)
"""
from datetime import date as Date
from datetime import timedelta

from django.db.models import Count, Exists, OuterRef, Q
from rest_framework.response import Response
from rest_framework.views import APIView


MAX_ELEMENTS = 50


def _nom_affaire(affaire):
    return f'{affaire.num_affaire} - {affaire.nom}' if affaire.num_affaire else affaire.nom


def _lien_marche(projet):
    return f'/marches/ajouter?affaire={projet.affaire_id}&prestation={projet.prestation_id}&projet={projet.id}'


def controles():
    """Liste des contrôles : code, titre, explication, gravité, nombre, éléments [{libelle, detail, lien}]."""
    from gsheets.models import LigneFeuille
    from marches.models import Affaire, Description, Prestation, Projet, Statut, Tache
    from pointages.calculs import est_ouvrable
    from pointages.models import PartPointage, Pointage

    resultats = []

    def ajouter(code, titre, explication, gravite, requete, element):
        nombre = requete.count()
        resultats.append({'code': code, 'titre': titre, 'explication': explication, 'gravite': gravite, 'nombre': nombre,
                          'elements': [element(x) for x in requete[:MAX_ELEMENTS]]})

    lignes = LigneFeuille.objects.filter(description__isnull=False).select_related(
        'feuille', 'description__projet__affaire', 'description__projet__prestation')
    element_ligne = lambda l: {
        'libelle': f'{l.feuille.nom}, ligne {l.numero} : {l.description.nom}',
        'detail': f'{_nom_affaire(l.description.projet.affaire)} › {l.description.projet.prestation.nom} › {l.description.projet.nom}',
        'lien': f'/google-sheet/feuilles/{l.feuille_id}'}

    # 1. Descriptions pointées mais dans aucune feuille : le temps n'est reporté nulle part
    hors_feuille = (Description.objects.filter(Exists(PartPointage.objects.filter(description=OuterRef('pk'))))
                    .exclude(Exists(LigneFeuille.objects.filter(description=OuterRef('pk'))))
                    .exclude(projet__affaire__pointage_seul=True)   # affaires « Pointage seulement »
                    .select_related('projet__affaire', 'projet__prestation').order_by('projet__affaire__nom', 'nom'))
    ajouter('description_hors_feuille', 'Descriptions pointées hors de toute feuille',
            'Du temps a été pointé, mais la description n’est dans aucune feuille : il n’est reporté nulle part '
            '(les affaires « Pointage seulement » ne sont pas signalées).', 'attention',
            hors_feuille, lambda d: {'libelle': d.nom, 'detail': f'{_nom_affaire(d.projet.affaire)} › {d.projet.prestation.nom} › {d.projet.nom}',
                                     'lien': _lien_marche(d.projet)})

    # 2. Lignes avec du temps de production mais sans Employé : leur quantité n'est attribuée à personne
    ajouter('temps_sans_employe', 'Lignes avec du temps mais sans Employé',
            'Le rendement ne peut être attribué à personne.', 'erreur',
            lignes.filter(temps_prod__gt=0, employe__isnull=True).order_by('feuille__nom', 'numero'), element_ligne)

    # 3. Lignes avec du temps mais sans Date de début (invisibles dans les graphiques datés en mode Feuilles)
    ajouter('sans_date_debut', 'Lignes avec du temps mais sans Date de début',
            'En mode « Données des feuilles », elles n’apparaissent ni dans Evolution, ni par mois.', 'info',
            lignes.filter(Q(temps_prod__gt=0) | Q(temps_controle__gt=0), date_debut__isnull=True).order_by('feuille__nom', 'numero'),
            element_ligne)

    # 4. Personnes placées sur une ligne sans être responsables ni membres de l'affaire
    hors_equipe = Q()
    for champ in ('employe', 'controleur', 'employe_reprise'):
        hors_equipe |= (Q(**{f'{champ}__isnull': False})
                        & ~Q(**{f'{champ}__in': Affaire.responsables.through.objects.filter(affaire_id=OuterRef('description__projet__affaire_id')).values('employe_id')})
                        & ~Q(**{f'{champ}__in': Affaire.membres.through.objects.filter(affaire_id=OuterRef('description__projet__affaire_id')).values('employe_id')}))
    ajouter('hors_equipe', 'Personnes placées hors de l’équipe de l’affaire',
            'Employé, Contrôleur ou Employé reprise qui n’est ni responsable ni membre de l’affaire (souvent un import).', 'attention',
            lignes.filter(hors_equipe).order_by('feuille__nom', 'numero'), element_ligne)

    # 5. Projets / communes sans description
    ajouter('projet_sans_description', 'Projets / communes sans description',
            'Rien à pointer ni à suivre dans les feuilles.', 'info',
            Projet.objects.annotate(n=Count('descriptions')).filter(n=0, affaire__actif=True)
            .select_related('affaire', 'prestation').order_by('affaire__nom', 'nom'),
            lambda p: {'libelle': p.nom, 'detail': f'{_nom_affaire(p.affaire)} › {p.prestation.nom}', 'lien': _lien_marche(p)})

    # 6. Descriptions sans quantité (pas de rendement, pas de Temps Estimatif)
    ajouter('description_sans_quantite', 'Descriptions sans quantité',
            'Pas de rendement ni de Temps Estimatif possible.', 'attention',
            Description.objects.filter(Q(quantite__isnull=True) | Q(quantite=0), projet__affaire__actif=True)
            .select_related('projet__affaire', 'projet__prestation').order_by('projet__affaire__nom', 'nom'),
            lambda d: {'libelle': d.nom, 'detail': f'{_nom_affaire(d.projet.affaire)} › {d.projet.prestation.nom} › {d.projet.nom}',
                       'lien': _lien_marche(d.projet)})

    # 7. Prestations sans rendement objectif
    ajouter('prestation_sans_objectif', 'Prestations sans rendement objectif',
            'Impossible d’y créer un projet / une commune.', 'erreur',
            Prestation.objects.annotate(n=Count('rendements')).filter(n=0).order_by('nom'),
            lambda p: {'libelle': p.nom, 'detail': f'Unité : {p.unite}', 'lien': '/marches/ajouter'})

    # 8. Affaires en cours sans responsable
    ajouter('affaire_sans_responsable', 'Affaires en cours sans responsable',
            'Personne ne peut gérer ses membres ni ses feuilles (hors administrateurs).', 'erreur',
            Affaire.objects.filter(actif=True).annotate(n=Count('responsables')).filter(n=0).order_by('nom'),
            lambda a: {'libelle': _nom_affaire(a), 'detail': '', 'lien': f'/marches/ajouter?affaire={a.id}'})

    # 9. Jours ouvrables pointés sans pause (60 derniers jours)
    depuis = Date.today() - timedelta(days=60)
    jours = (Pointage.objects.filter(date__gte=depuis).values('employe_id', 'employe__code_barre', 'employe__prenom_usuel',
                                                              'employe__prenom', 'date')
             .annotate(pauses=Count('id', filter=Q(pause=True))).filter(pauses=0).order_by('-date'))
    jours = [j for j in jours if est_ouvrable(j['date'])]
    resultats.append({
        'code': 'sans_pause', 'titre': 'Jours pointés sans pause (60 derniers jours)',
        'explication': 'Jour ouvrable pointé sans la case « Pause (−1 h) » : la H_Durée compte une heure de trop.',
        'gravite': 'attention', 'nombre': len(jours),
        'elements': [{'libelle': f"{j['employe__code_barre']}_{j['employe__prenom_usuel'] or j['employe__prenom']}",
                      'detail': f"{j['date']:%d/%m/%Y}", 'lien': '/pointages/suivi'} for j in jours[:MAX_ELEMENTS]],
    })

    # 10. Réglages manquants
    reglages = []
    if not Statut.defaut():
        reglages.append({'libelle': 'Aucun statut « Par défaut »', 'detail': 'Les nouvelles lignes n’ont pas de statut.', 'lien': '/marches/ajouter'})
    if not Statut.pour_note_rendement():
        reglages.append({'libelle': 'Aucun statut « Active la note de rendement »', 'detail': 'La note s’affiche toujours, sans attendre la fin du projet.', 'lien': '/marches/ajouter'})
    for type_tache, libelle in (('PRODUCTION', 'Production'), ('CONTROLE', 'Contrôle')):
        if not Tache.objects.filter(type=type_tache).exists():
            reglages.append({'libelle': f'Aucune tâche de type « {libelle} »', 'detail': 'Ce temps ne peut pas être reporté dans les feuilles.', 'lien': '/marches/ajouter'})
    # Sécurité : vérification des certificats HTTPS (Keycloak, API RH)
    from django.conf import settings
    if settings.CA_BUNDLE is False:
        reglages.append({'libelle': 'Vérification des certificats HTTPS désactivée (CA_BUNDLE=desactive)',
                         'detail': 'Keycloak et l’API RH ne sont pas authentifiés : renseigner CA_BUNDLE=systeme ou le chemin '
                                   'du certificat .pem dans le fichier .env du serveur.', 'lien': ''})
    resultats.append({'code': 'reglages', 'titre': 'Réglages manquants', 'explication': 'Paramètres utiles au bon fonctionnement.',
                      'gravite': 'attention', 'nombre': len(reglages), 'elements': reglages})
    return resultats


class ControlesView(APIView):
    """Module « Paramètres > Contrôles de cohérence » de Paramètres > Autorisation (superadmin, ou par un rôle)."""
    module = 'parametres_controles'

    def get(self, request):
        liste = controles()
        return Response({'total': sum(c['nombre'] for c in liste), 'controles': liste})
