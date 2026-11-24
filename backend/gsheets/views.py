# backend/gsheets/views.py
"""
API des feuilles (préfixe /api/gsheets/)

  feuilles/                         mes feuilles (créateur, responsable ou membre d'une des affaires)
                                    POST : créer (réservé aux responsables des affaires choisies)
  feuilles/<id>/                    détail ; PATCH / DELETE : créateur, responsables, administrateurs
  feuilles/affaires-disponibles/    affaires dont je suis responsable, avec leurs prestations cochées
  feuilles/<id>/personnes/          responsables + membres de chaque affaire (listes Employé / Contrôleur)
  lignes/?feuille=<id>              lignes de la feuille (?search= ?statut= ?employe= ?affaire=)
  lignes/<id>/                      PATCH : saisie d'une ligne (+ « notes_saisies »: {critere_id: note})
  lignes/exporter/                  export Excel des colonnes affichées
  feuilles/modele/ · feuilles/importer/                      import de feuilles (créées ou mises à jour par nom)
  lignes/modele/?feuille=<id> · lignes/importer/?feuille=<id>  modèle prérempli et import des données d'une feuille
  lignes/suivi/                     POST {"feuille", "depuis", "edition": {"ligne", "champ"} | null}
                                    suivi en direct : lignes modifiées depuis « depuis » + qui modifie quoi
  historique/?feuille=<id>&ligne=<id>   historique des modifications (chargé à la demande)
"""
from datetime import datetime

from django.db.models import Avg, Count, Prefetch
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework import serializers

from autorisations.acces import q_visible
from ikarama.importation import ColonneImport, ImportExcelMixin, separer
from ikarama.vues import ExportExcelMixin, FiltresMixin
from marches.models import Affaire, AffairePrestation, Statut
from utilisateurs.models import Employe
from utilisateurs.serializers import EmployeResumeSerializer

from . import presence
from pointages.models import PartPointage

from .models import Feuille, HistoriqueLigne, LigneFeuille, NoteCritere, PerimetreFeuille
from .serializers import FeuilleSerializer, HistoriqueSerializer, LigneSerializer
from .services import (affaires_creables, droit_feuille, feuilles_de, feuilles_visibles, peut_gerer, personnes_de_l_affaire,
                       synchroniser, verifier_droit_feuille)


def moi(request):
    return getattr(request.user, 'employe', None)


class FeuilleViewSet(ImportExcelMixin, ExportExcelMixin, viewsets.ModelViewSet):
    # Paramètres > Autorisation : Google Sheet > Mes feuilles (Créer = page « Créer une nouvelle feuille »)
    module = 'gsheets_feuilles'
    serializer_class = FeuilleSerializer
    search_fields = ['nom', 'perimetres__affaire__nom', 'perimetres__affaire__num_affaire']
    ordering_fields = ['nom', 'cree_le', 'modifie_le']
    ordering = ['-cree_le']
    verbes_actions = {'affaires_disponibles': 'creer', 'personnes': 'voir', 'equipe': 'voir', 'modele': 'importer',
                      'importer': 'importer', 'exporter': 'exporter'}

    def lignes_export(self):
        """Export de la liste des feuilles : celles des affaires du périmètre « Exporter »."""
        from autorisations.droits import q_droit
        feuilles = self.filter_queryset(self.get_queryset()).filter(
            q_droit(self.request.user, 'gsheets_feuilles', 'exporter', 'perimetres__affaire__')).distinct()
        return self.get_serializer(feuilles, many=True).data

    # --- Import Excel : une ligne = une feuille + une prestation d'une affaire ------------
    import_nom = 'Feuilles'
    import_cle_groupe = 'nom'
    import_colonnes = [
        ColonneImport('nom', 'Nom feuille', requis=True, largeur=30, exemple='Suivi novembre',
                      aide='Les lignes qui portent le même nom forment une seule feuille. Si vous gérez déjà une feuille '
                           'de ce nom, elle est mise à jour (ses affaires et prestations sont remplacées par celles du fichier).'),
        ColonneImport('affaire', 'ID affaire', requis=True, largeur=12, exemple='12',
                      aide='Numéro de l’affaire (onglet « Affaires ») : vous devez en être responsable.'),
        ColonneImport('prestation', 'Prestation', requis=True, largeur=26, exemple='Saisie de fiches',
                      aide='Nom d’une prestation cochée pour cette affaire (onglet « Affaires »).'),
        ColonneImport('utiliser_criteres', 'Utiliser critères', largeur=16, exemple='Oui',
                      aide='Oui ou Non (première ligne de la feuille). Vide : Oui pour une nouvelle feuille, inchangé sinon.'),
        ColonneImport('criteres', 'Critères de CTRL', largeur=40, exemple='Orthographe; Exhaustivité',
                      aide='Commentaires des critères séparés par « ; » (première ligne de la feuille). Vide : aucun pour une nouvelle feuille, inchangés sinon.'),
    ]
    import_alias = {'perimetres_saisis': 'prestation', 'criteres_saisis': 'criteres'}

    def import_onglets_reference(self):
        employe = moi(self.request)
        affaires = affaires_creables(employe, self.request.user).order_by('ordre', 'id') if employe else []
        return [('Affaires', ['ID affaire', 'Num affaire', 'Nom affaire', 'Prestations cochées'],
                 [(a.id, a.num_affaire, a.nom, '; '.join(l.prestation.nom for l in a.liens_prestations.all())) for a in affaires])]

    def importer_ligne(self, lignes):
        nom = str(lignes[0].get('nom') or '').strip()
        if not nom:
            raise serializers.ValidationError({'nom': 'Ce champ est obligatoire.'})
        paires, erreurs = [], []
        for valeurs in lignes:
            try:
                affaire_id = int(str(valeurs.get('affaire')).strip())
            except ValueError:
                erreurs.append(f"ID affaire invalide : « {valeurs.get('affaire')} »")
                continue
            lien = (AffairePrestation.objects.filter(affaire_id=affaire_id, prestation__nom__iexact=str(valeurs.get('prestation') or '').strip())
                    .first())
            if lien is None:
                erreurs.append(f"la prestation « {valeurs.get('prestation')} » n'est pas cochée pour l'affaire {affaire_id}")
            else:
                paires.append({'affaire': affaire_id, 'prestation': lien.prestation_id})
        if erreurs:
            raise serializers.ValidationError({'prestation': erreurs})

        premiere = lambda cle: next((v.get(cle) for v in lignes if str(v.get(cle) or '').strip()), None)
        utiliser = premiere('utiliser_criteres')
        criteres = premiere('criteres')
        donnees = {'nom': nom, 'perimetres_saisis': paires}
        if utiliser is not None:
            donnees['utiliser_criteres'] = str(utiliser).strip().lower() in ('oui', 'o', 'yes', 'vrai', '1', 'true')
        if criteres is not None:
            donnees['criteres_saisis'] = separer(criteres)

        existante = next((f for f in self.get_queryset().filter(nom__iexact=nom) if droit_feuille(self.request.user, f, 'modifier')), None)
        serializer = FeuilleSerializer(existante, data=donnees, partial=bool(existante), context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        feuille = serializer.save() if existante else serializer.save(cree_par=moi(self.request))
        return ('modification' if existante else 'creation'), f"{feuille.nom} ({len(paires)} prestation(s))"

    def get_queryset(self):
        return (feuilles_visibles(self.request.user)
                .select_related('cree_par')
                .prefetch_related(
                    Prefetch('perimetres', queryset=PerimetreFeuille.objects.select_related('affaire', 'prestation')),
                    'perimetres__affaire__responsables', 'criteres')
                .annotate(nb_lignes=Count('lignes', distinct=True), avancement_moyen=Avg('lignes__avancement')))

    def perform_create(self, serializer):
        serializer.save(cree_par=moi(self.request))

    def perform_update(self, serializer):
        verifier_droit_feuille(self.request.user, serializer.instance, 'modifier')
        serializer.save()

    def perform_destroy(self, instance):
        verifier_droit_feuille(self.request.user, instance, 'supprimer')
        instance.delete()

    def retrieve(self, request, *args, **kwargs):
        feuille = self.get_object()
        synchroniser(feuille)   # rattrape les descriptions ajoutées entre-temps
        return Response(self.get_serializer(self.get_queryset().get(pk=feuille.pk)).data)

    @action(detail=False, methods=['get'], url_path='affaires-disponibles')
    def affaires_disponibles(self, request):
        employe = moi(request)
        if employe is None:
            return Response([])
        # Pour chaque prestation : projets, descriptions (= lignes créées) et feuille qui la contient déjà
        from django.db.models import Count

        from marches.models import Projet
        affaires = list(affaires_creables(employe, request.user).order_by('ordre', 'id'))
        comptes = {(c['affaire_id'], c['prestation_id']): c for c in Projet.objects.filter(affaire__in=affaires)
                   .values('affaire_id', 'prestation_id').annotate(projets=Count('id', distinct=True),
                                                                   descriptions=Count('descriptions', distinct=True))}
        feuille_courante = request.query_params.get('feuille')
        prises = {(p.affaire_id, p.prestation_id): p.feuille.nom for p in PerimetreFeuille.objects.filter(affaire__in=affaires)
                  .exclude(feuille_id=feuille_courante if str(feuille_courante or '').isdigit() else None).select_related('feuille')}
        return Response([
            {
                'id': a.id, 'num_affaire': a.num_affaire, 'nom': a.nom,
                'prestations': [{
                    'id': l.prestation_id, 'nom': l.prestation.nom, 'unite': l.prestation.unite,
                    'nb_projets': comptes.get((a.id, l.prestation_id), {}).get('projets', 0),
                    'nb_descriptions': comptes.get((a.id, l.prestation_id), {}).get('descriptions', 0),
                    'deja_dans': prises.get((a.id, l.prestation_id)),
                } for l in a.liens_prestations.all()],
            }
            for a in affaires
        ])

    @action(detail=True, methods=['get'])
    def equipe(self, request, pk=None):
        """Responsables et membres de chaque affaire de la feuille (bouton « œil » de Mes feuilles)."""
        feuille = self.get_object()
        affaires = sorted({p.affaire for p in feuille.perimetres.select_related('affaire')}, key=lambda a: a.nom)
        return Response([{
            'id': a.id, 'num_affaire': a.num_affaire, 'nom': a.nom,
            'responsables': EmployeResumeSerializer(a.responsables.filter(q_visible()).order_by('nom', 'prenom'), many=True).data,
            'membres': EmployeResumeSerializer(a.membres.filter(q_visible()).order_by('nom', 'prenom'), many=True).data,
        } for a in affaires])

    @action(detail=True, methods=['get'])
    def personnes(self, request, pk=None):
        feuille = self.get_object()
        affaires = {p.affaire for p in feuille.perimetres.all()}
        return Response({
            str(a.id): EmployeResumeSerializer(personnes_de_l_affaire(a), many=True).data for a in affaires
        })


class LigneViewSet(ImportExcelMixin, FiltresMixin, ExportExcelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                   mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Les lignes se créent et se suppriment toutes seules (synchronisation avec le Marché)."""
    module = 'gsheets'
    serializer_class = LigneSerializer
    search_fields = ['description__nom', 'description__projet__nom', 'description__projet__affaire__nom',
                     'description__projet__affaire__num_affaire', 'employe__nom', 'employe__prenom',
                     'employe__code_barre', 'commentaires']
    ordering_fields = ['numero', 'avancement', 'nb_reprises', 'modifie_le']
    ordering = ['numero']
    filtres = {
        'feuille': 'feuille_id', 'statut': 'statut_id', 'statut_controle': 'statut_controle_id', 'employe': 'employe_id', 'controleur': 'controleur_id',
        'affaire': 'description__projet__affaire_id',
    }
    verbes_actions = {'exporter': 'voir', 'suivi': 'voir', 'modele': 'voir', 'importer': 'modifier'}
    MAX_SUIVI = 200

    # --- Import Excel des données d'une feuille (modèle prérempli avec les lignes actuelles) ---
    import_nom = 'Lignes'
    CHAMPS_TEXTE = ('commentaires', 'commentaires_controle', 'commentaires_reprise')
    PERSONNES = ('employe', 'controleur', 'employe_reprise')

    def _feuille_import(self):
        feuille = feuilles_visibles(self.request.user).filter(pk=self.request.query_params.get('feuille')).first()
        if feuille is None:
            raise serializers.ValidationError({'fichier': 'Feuille introuvable (?feuille=<id>).'})
        # Données de la feuille (ses lignes) : règle métier, créateur ou responsable d'une de ses affaires
        if self.action in ('importer', 'modele') and not peut_gerer(self.request.user, feuille):
            raise PermissionDenied('Seuls le créateur de la feuille et les responsables de ses affaires importent ses données.')
        return feuille

    def get_import_colonnes(self):
        feuille = self._feuille_import()
        aide_personne = 'Matricule (ex. PR00123). Vide : personne.'
        colonnes = [
            ColonneImport('numero', 'ID ligne', requis=True, largeur=9, aide='Ne pas modifier : désigne la ligne de la feuille.'),
            *[ColonneImport(cle, libelle, lecture_seule=True, largeur=largeur) for cle, libelle, largeur in (
                ('num_affaire', 'Num affaire', 12), ('nom_affaire', 'Nom affaire', 24), ('prestation', 'Prestation', 20),
                ('projet', 'Projet / Commune', 22), ('description', 'Description', 24), ('quantite', 'Quantité', 10),
                ('unite', 'Unité', 10))],
            ColonneImport('employe', 'Employé', aide=aide_personne, largeur=14),
            ColonneImport('statut', 'Statut', aide='Nom d’un statut (Marchés > Statuts). Vide : aucun.', largeur=14),
            ColonneImport('avancement', 'Avancement', aide='Nombre de 0 à 100 (%).', largeur=12),
            ColonneImport('commentaires', 'Commentaires', largeur=30),
            ColonneImport('controleur', 'Contrôleur', aide=aide_personne, largeur=14),
            ColonneImport('statut_controle', 'Statut de contrôle', aide='Nom d’un statut (Marchés > Statuts). Vide : aucun.', largeur=16),
            ColonneImport('commentaires_controle', 'Commentaires contrôle', largeur=30),
            ColonneImport('nb_reprises', 'Nombre de reprises', aide='Réservé aux responsables.', largeur=12),
            ColonneImport('employe_reprise', 'Employé reprise', aide=aide_personne, largeur=14),
            ColonneImport('commentaires_reprise', 'Commentaires reprise', largeur=30),
        ]
        if feuille.utiliser_criteres:
            colonnes += [ColonneImport(f'critere_{c.id}', f'Critère {c.numero}', largeur=11,
                                       aide=f'{c.commentaire} : note de 1 à 5 (réservé aux responsables).')
                         for c in feuille.criteres.all()]
        return colonnes

    def import_lignes_modele(self):
        feuille = self._feuille_import()
        resultat = []
        for ligne in self.get_queryset().filter(feuille=feuille).order_by('numero'):
            marche = LigneSerializer(ligne, context=self.get_serializer_context()).get_marche(ligne)
            notes = {f'critere_{n.critere_id}': float(n.note) for n in ligne.notes.all() if n.note is not None}
            resultat.append({
                'numero': ligne.numero, **{k: marche.get(k) for k in ('num_affaire', 'nom_affaire', 'prestation', 'projet', 'description', 'unite')},
                'quantite': float(marche['quantite']) if marche.get('quantite') else None,
                **{c: getattr(ligne, c).code_barre if getattr(ligne, c) else None for c in self.PERSONNES},
                'statut': ligne.statut.nom if ligne.statut else None, 'avancement': ligne.avancement,
                'statut_controle': ligne.statut_controle.nom if ligne.statut_controle else None,
                **{c: getattr(ligne, c) for c in self.CHAMPS_TEXTE}, 'nb_reprises': ligne.nb_reprises, **notes,
            })
        return resultat

    def _personne(self, valeur, colonne):
        texte = str(valeur or '').strip()
        if not texte:
            return None
        matricule = texte.split('_')[0].upper()
        employe = Employe.objects.filter(q_visible()).filter(code_barre__iexact=matricule).first()
        if employe is None:
            raise serializers.ValidationError({colonne: f'matricule inconnu : « {texte} »'})
        return employe

    def importer_ligne(self, valeurs):
        feuille = self._feuille_import()
        try:
            numero = int(str(valeurs.get('numero')).strip())
        except ValueError:
            raise serializers.ValidationError({'numero': f"ID de ligne invalide : « {valeurs.get('numero')} »"})
        ligne = self.get_queryset().filter(feuille=feuille, numero=numero).first()
        if ligne is None:
            raise serializers.ValidationError({'numero': f'Aucune ligne n°{numero} dans cette feuille.'})
        libelle = f"Ligne {numero} – {LigneSerializer(ligne, context=self.get_serializer_context()).get_marche(ligne).get('description')}"

        changements = {}
        for champ in self.PERSONNES:
            if champ in valeurs:
                personne = self._personne(valeurs[champ], champ)
                if (personne.pk if personne else None) != getattr(ligne, f'{champ}_id'):
                    changements[champ] = personne.pk if personne else None
        for champ in ('statut', 'statut_controle'):
            if champ not in valeurs:
                continue
            nom = str(valeurs[champ] or '').strip()
            statut = Statut.objects.filter(nom__iexact=nom).first() if nom else None
            if nom and statut is None:
                raise serializers.ValidationError({champ: f'statut inconnu : « {nom} »'})
            if (statut.pk if statut else None) != getattr(ligne, f'{champ}_id'):
                changements[champ] = statut.pk if statut else None
        if 'avancement' in valeurs and valeurs['avancement'] not in (None, ''):
            brut = valeurs['avancement']
            avancement = round(brut * 100) if isinstance(brut, float) and 0 < brut <= 1 else int(float(str(brut).replace('%', '').replace(',', '.')))
            if avancement != ligne.avancement:
                changements['avancement'] = avancement
        for champ in self.CHAMPS_TEXTE:
            if champ in valeurs and str(valeurs[champ] or '').strip() != (getattr(ligne, champ) or '').strip():
                changements[champ] = str(valeurs[champ] or '').strip()
        if 'nb_reprises' in valeurs and valeurs['nb_reprises'] not in (None, '') and int(float(valeurs['nb_reprises'])) != ligne.nb_reprises:
            changements['nb_reprises'] = int(float(valeurs['nb_reprises']))
        notes_actuelles = {n.critere_id: n.note for n in ligne.notes.all()}
        notes = {}
        for cle, valeur in valeurs.items():
            if cle.startswith('critere_'):
                critere_id = int(cle.split('_')[1])
                actuelle = notes_actuelles.get(critere_id)
                nouvelle = None if valeur in (None, '') else float(str(valeur).replace(',', '.'))
                if (float(actuelle) if actuelle is not None else None) != nouvelle:
                    notes[str(critere_id)] = '' if nouvelle is None else str(nouvelle)
        if notes:
            changements['notes_saisies'] = notes

        if not changements:
            return 'inchange', libelle
        serializer = LigneSerializer(ligne, data=changements, partial=True, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return 'modification', libelle

    def get_queryset(self):
        return (LigneFeuille.objects.filter(feuille__in=feuilles_visibles(self.request.user))
                .select_related('feuille', 'statut', 'statut_controle', 'employe', 'controleur', 'employe_reprise', 'modifie_par',
                                'description__projet__affaire', 'description__projet__prestation',
                                'description__projet__rendement')
                .prefetch_related(Prefetch('notes', queryset=NoteCritere.objects.all()),
                                  Prefetch('parts_pointage', queryset=PartPointage.objects.select_related('pointage__tache'))))

    def list(self, request, *args, **kwargs):
        if not request.query_params.get('feuille'):
            return Response({'detail': 'Précisez la feuille (?feuille=<id>).'}, status=status.HTTP_400_BAD_REQUEST)
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=['post'])
    def suivi(self, request):
        """
        Appelé toutes les quelques secondes par la feuille ouverte :
          - signale la case que je modifie (ou aucune) ;
          - renvoie les lignes modifiées depuis « depuis » et qui modifie quoi.
        """
        feuille = feuilles_visibles(request.user).filter(pk=request.data.get('feuille')).first()
        if feuille is None:
            return Response({'detail': 'Feuille introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        edition = request.data.get('edition') or {}
        if presence.signaler(feuille.pk, moi(request), edition.get('ligne'), edition.get('champ')):
            from temps_reel.diffusion import presence_modifiee
            presence_modifiee(feuille.pk)   # les autres le voient aussitôt

        maintenant = timezone.now()
        lignes, recharger = [], False
        depuis = request.data.get('depuis')
        try:
            depuis = datetime.fromisoformat(depuis) if depuis else None
        except ValueError:
            depuis = None
        if depuis is not None:
            if timezone.is_naive(depuis) != timezone.is_naive(maintenant):
                depuis = depuis.replace(tzinfo=None) if timezone.is_naive(maintenant) else timezone.make_aware(depuis)
            modifiees = self.get_queryset().filter(feuille=feuille, modifie_le__gt=depuis).order_by('modifie_le')
            if modifiees.count() > self.MAX_SUIVI:
                recharger = True   # trop de changements : la page se recharge entièrement
            else:
                lignes = self.get_serializer(modifiees, many=True).data
        return Response({
            'maintenant': maintenant.isoformat(),
            'lignes': lignes,
            'recharger': recharger,
            'nb_lignes': feuille.lignes.count(),
            'presences': presence.lire(feuille.pk, sauf=moi(request)),
        })


class HistoriqueViewSet(FiltresMixin, ExportExcelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Historique des modifications : toujours filtré par feuille (et éventuellement par ligne)."""
    module = 'gsheets'
    serializer_class = HistoriqueSerializer
    search_fields = ['libelle', 'ancienne_valeur', 'nouvelle_valeur', 'auteur__nom', 'auteur__code_barre']
    ordering_fields = ['date']
    ordering = ['-date', '-id']
    filtres = {'feuille': 'feuille_id', 'ligne': 'ligne_id', 'auteur': 'auteur_id'}
    verbes_actions = {'exporter': 'voir'}

    def get_queryset(self):
        return (HistoriqueLigne.objects.filter(feuille__in=feuilles_visibles(self.request.user))
                .select_related('auteur', 'ligne__description'))

    def list(self, request, *args, **kwargs):
        if not request.query_params.get('feuille'):
            return Response({'detail': 'Précisez la feuille (?feuille=<id>).'}, status=status.HTTP_400_BAD_REQUEST)
        return super().list(request, *args, **kwargs)


class ParametresTempsEstimatifView(APIView):
    """
    Paramètres > Temps Estimatif. Lecture : toute personne qui voit les feuilles ; modification : administrateurs.
    """
    module = 'gsheets'

    @staticmethod
    def _donnees(p):
        from rendements.models import ParametresRendement
        return {'unite': p.unite, 'marge': p.marge, 'couleur_rouge': p.couleur_rouge, 'couleur_orange': p.couleur_orange,
                'heures_par_jour': float(ParametresRendement.actuels().heures_par_jour)}

    def get(self, request):
        from .models import ParametresTempsEstimatif
        return Response(self._donnees(ParametresTempsEstimatif.actuels()))

    def put(self, request):
        import re

        from autorisations.permissions import est_administrateur

        from .models import ParametresTempsEstimatif
        if not est_administrateur(request.user):
            return Response({'detail': 'Réservé aux administrateurs.'}, status=403)
        p = ParametresTempsEstimatif.actuels()
        erreurs = {}
        unite = request.data.get('unite', p.unite)
        if unite not in ('heures', 'jours'):
            erreurs['unite'] = ['Heures ou jours.']
        try:
            marge = int(request.data.get('marge', p.marge))
            assert 0 <= marge <= 99
        except (TypeError, ValueError, AssertionError):
            erreurs['marge'] = ['Nombre entier de 0 à 99.']
            marge = p.marge
        couleurs = {}
        for champ in ('couleur_rouge', 'couleur_orange'):
            valeur = str(request.data.get(champ, getattr(p, champ))).strip()
            if not re.fullmatch(r'#[0-9A-Fa-f]{6}', valeur):
                erreurs[champ] = ['Couleur au format #RRGGBB.']
            couleurs[champ] = valeur.upper()
        if erreurs:
            return Response(erreurs, status=400)
        p.unite, p.marge = unite, marge
        for champ, valeur in couleurs.items():
            setattr(p, champ, valeur)
        p.save()
        return Response(self._donnees(p))


class MonResumeView(APIView):
    """
    Profil : résumé des lignes de feuille où la personne est « Employé », par affaire et prestation :
    nombre de lignes, quantité, moyenne des Notes de rendement et des Notes de qualité (lignes notées seulement).
    """
    module = 'gsheets'

    def get(self, request):
        from decimal import Decimal, InvalidOperation

        moi = getattr(request.user, 'employe', None)
        if moi is None:
            return Response({'groupes': [], 'note_rendement': None, 'note_qualite': None, 'nb_lignes': 0})
        lignes = (LigneFeuille.objects.filter(employe=moi, description__isnull=False)
                  .select_related('feuille', 'statut', 'description__projet__affaire', 'description__projet__prestation',
                                  'description__projet__rendement')
                  .prefetch_related('notes', 'feuille__criteres'))
        serializer = LigneSerializer(context={'request': request})

        def nombre(texte):
            try:
                return float(Decimal(str(texte))) if texte not in (None, '', '—') else None
            except (InvalidOperation, ValueError):
                return None

        groupes, toutes_r, toutes_q = {}, [], []
        for ligne in lignes:
            projet = ligne.description.projet
            cle = (projet.affaire_id, projet.prestation_id)
            g = groupes.setdefault(cle, {
                'affaire': f'{projet.affaire.num_affaire} - {projet.affaire.nom}' if projet.affaire.num_affaire else projet.affaire.nom,
                'prestation': projet.prestation.nom, 'unite': projet.prestation.unite,
                'nb_lignes': 0, 'quantite': 0.0, 'notes_r': [], 'notes_q': [],
            })
            g['nb_lignes'] += 1
            g['quantite'] += float(ligne.description.quantite or 0)
            r, q = nombre(serializer.get_note_rendement(ligne)), nombre(serializer.get_note_qualite(ligne))
            if r is not None:
                g['notes_r'].append(r)
                toutes_r.append(r)
            if q is not None:
                g['notes_q'].append(q)
                toutes_q.append(q)
        moyenne = lambda liste: round(sum(liste) / len(liste), 2) if liste else None
        return Response({
            'nb_lignes': sum(g['nb_lignes'] for g in groupes.values()),
            'note_rendement': moyenne(toutes_r), 'note_qualite': moyenne(toutes_q),
            'nb_notes_rendement': len(toutes_r), 'nb_notes_qualite': len(toutes_q),
            'groupes': sorted([{
                'affaire': g['affaire'], 'prestation': g['prestation'], 'unite': g['unite'],
                'nb_lignes': g['nb_lignes'], 'quantite': g['quantite'],
                'note_rendement': moyenne(g['notes_r']), 'note_qualite': moyenne(g['notes_q']),
                'nb_notes_rendement': len(g['notes_r']), 'nb_notes_qualite': len(g['notes_q']),
            } for g in groupes.values()], key=lambda g: (g['affaire'], g['prestation'])),
        })


class StatutsFeuilleView(APIView):
    """Les statuts proposés dans les feuilles (lecture pour tous : le catalogue, lui, se gère dans Marchés > Statuts)."""
    def get(self, request):
        from marches.models import Statut
        return Response([{'id': st.id, 'nom': st.nom, 'couleur': st.couleur} for st in Statut.objects.order_by('ordre', 'id')])
