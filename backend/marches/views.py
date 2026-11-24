# backend/marches/views.py
"""
API du Marché (préfixe /api/marches/). Chaque ressource propose aussi :
  POST <ressource>/reordonner/   ordre manuel (poignées ≡)
  GET  <ressource>/exporter/     export Excel des colonnes affichées

  affaires/                      ?search=  ?responsable=<id>  ?membre=<id>     (DELETE = archivage)
                                 ?mes=1      : affaires dont je suis responsable ou membre (« Mes marchés »)
                                 ?archives=1 : affaires archivées (« Archives »)
  affaires/<id>/prestations/     POST {"prestation": id, "coche": true|false}
  affaires/<id>/membres/         POST {"membres": [ids]}  (responsables de l'affaire et administrateurs)
  affaires/<id>/desarchiver/     POST
  affaires/<id>/supprimer/       POST  suppression définitive, refusée s'il reste des prestations cochées,
                                       des projets / communes ou des descriptions
  affaires/modele/ · affaires/importer/         import Excel (voir ikarama/importation.py)
  prestations/modele/ · prestations/importer/
  prestations/                   ?affaire=<id> ajoute « cochee » ; ?cochees=1 garde seulement les cochées
  projets/                       ?affaire=<id>&prestation=<id>     (quantité = somme des descriptions)
  descriptions/                  ?projet=<id>   descriptions d'un projet, avec leur quantité
  taches/
  statuts/
"""
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from autorisations.droits import q_droit, verifier
from autorisations.permissions import est_administrateur

from autorisations.acces import q_visible
from ikarama.importation import ColonneImport, ImportExcelMixin, separer
from ikarama.vues import ActifMixin, ExportExcelMixin, ModeleViewSet, OrdreMixin, VRAI
from utilisateurs.models import Employe

from .models import Affaire, AffairePrestation, Description, Prestation, Projet, Statut, Tache
from .serializers import (AffaireSerializer, DescriptionSerializer, PersonnesField, PrestationSerializer,
                          ProjetSerializer, StatutSerializer, TacheSerializer)


def entier(valeur):
    return int(valeur) if str(valeur or '').isdigit() else None


class BaseMarche(OrdreMixin, ExportExcelMixin, ModeleViewSet):
    module = 'marches'
    ordering = ['ordre', 'id']
    ordering_fields = ['ordre', 'id', 'nom', 'cree_le']
    search_fields = ['nom']
    verbes_actions = {'reordonner': 'modifier', 'exporter': 'voir'}

    def perform_create(self, serializer):
        serializer.save(cree_par=getattr(self.request.user, 'employe', None))

    def perform_destroy(self, instance):
        # Point de sauvegarde : si la suppression est refusée en cours de route (ex. une feuille
        # contient des données sur une description), tout est annulé proprement.
        with transaction.atomic():
            instance.delete()

    def cochage(self, request, lien_modele, filtre_lien, message_utilise=None, est_utilise=None):
        """Coche / décoche un élément d'un catalogue pour un parent (affaire ou projet)."""
        coche = str(request.data.get('coche', 'true')).lower() in VRAI
        if coche:
            lien_modele.objects.get_or_create(**filtre_lien)
        else:
            if est_utilise and est_utilise():
                return Response({'detail': message_utilise}, status=status.HTTP_400_BAD_REQUEST)
            lien_modele.objects.filter(**filtre_lien).delete()
        return Response({'coche': coche})


class AffaireViewSet(ImportExcelMixin, ActifMixin, BaseMarche):
    serializer_class = AffaireSerializer
    search_fields = ['nom', 'num_affaire']
    ordering_fields = BaseMarche.ordering_fields + ['num_affaire']
    filtres = {'responsable': 'responsables', 'membre': 'membres'}
    verbes_actions = {**BaseMarche.verbes_actions, 'prestations': 'modifier', 'membres': 'modifier',
                      'desarchiver': 'desarchiver', 'supprimer': 'supprimer', 'modele': 'voir', 'importer': 'importer',
                      'exporter': 'exporter', 'destroy': 'archiver'}

    # --- Paramètres > Autorisation ---------------------------------------------
    #   Mes marchés (?mes=1, lecture) : responsables et membres, sans droit particulier ;
    #   Archives (?archives=1, désarchiver, suppression définitive) : module « Marchés > Archives » ;
    #   le reste : module « Marchés > Affaires ». DELETE = archiver.
    #   Membres (Mes marchés) : règle métier, les responsables de l'affaire (ou « Affaires > Modifier »).
    @property
    def module(self):
        requete = getattr(self, 'request', None)
        parametres = requete.query_params if requete is not None else {}
        if self.action == 'membres':
            return None
        if self.action in ('list', 'retrieve', 'exporter') and parametres.get('mes', '').lower() in VRAI:
            return None
        if self.action in ('desarchiver', 'supprimer') or parametres.get('archives', '').lower() in VRAI:
            return 'marches_archives'
        return 'marches_affaires'

    def _verbe(self):
        from autorisations.permissions import verbe_de_la_requete
        return verbe_de_la_requete(self.request, self)

    def get_object(self):
        objet = super().get_object()
        if self.module:
            verifier(self.request.user, self.module, self._verbe(), objet)
        return objet

    # --- Import Excel -------------------------------------------------------
    import_nom = 'Affaires'
    import_colonnes = [
        ColonneImport('num_affaire', 'Num affaire', aide='Facultatif. Si UNE affaire porte déjà ce n°, elle est mise à jour ; si aucune, une affaire est créée ; si plusieurs, la ligne est refusée.', exemple='AF-2026-01', largeur=16),
        ColonneImport('nom', 'Nom affaire', requis=True, exemple='Recensement Analamanga', largeur=34),
        ColonneImport('responsables', 'Responsables', requis=True, aide='Matricules séparés par « ; » (voir l’onglet Personnes).', exemple='PR00001; PR00002', largeur=26),
        ColonneImport('membres', 'Membres', requis=True, aide='Matricules séparés par « ; », ou TOUS pour toutes les personnes ayant accès au site.', exemple='PR00010; PR00011', largeur=30),
        ColonneImport('prestations', 'Prestations', aide='Facultatif. Noms des prestations à cocher, séparés par « ; » (voir l’onglet Prestations). Les prestations déjà cochées restent cochées.', exemple='Saisie de fiches; Contrôle qualité', largeur=34),
    ]
    import_explications = ['Responsables et membres doivent avoir accès au site.']

    def import_onglets_reference(self):
        personnes = Employe.objects.filter(q_visible()).exclude(code_barre__isnull=True).order_by('nom', 'prenom')
        return [
            ('Personnes', ['Matricule', 'Nom', 'Employé'], [(e.code_barre, e.nom_affiche, e.identifiant) for e in personnes]),
            ('Prestations', ['Nom prestation', 'Unité'], Prestation.objects.order_by('ordre', 'id').values_list('nom', 'unite')),
        ]

    def _personnes(self, valeur, colonne, accepter_tous=False):
        visibles = Employe.objects.filter(q_visible())
        if accepter_tous and str(valeur or '').strip().upper() in ('TOUS', 'TOUT LE MONDE'):
            return list(visibles.values_list('pk', flat=True))
        matricules = separer(valeur)
        trouves = {e.code_barre.upper(): e.pk for e in visibles.filter(code_barre__in=[m.upper() for m in matricules] + matricules)}
        inconnus = [m for m in matricules if m.upper() not in trouves]
        if inconnus:
            raise serializers.ValidationError({colonne: f"matricule(s) inconnu(s) ou sans accès au site : {', '.join(inconnus)}"})
        return [trouves[m.upper()] for m in matricules]

    def importer_ligne(self, valeurs):
        num = str(valeurs.get('num_affaire') or '').strip()
        existantes = list(Affaire.objects.filter(num_affaire=num)[:2]) if num else []
        if len(existantes) > 1:
            raise serializers.ValidationError(
                f"Plusieurs affaires portent le n° {num} : impossible de savoir laquelle mettre à jour. "
                "Modifiez-la depuis le tableau, ou laissez le n° vide pour créer une nouvelle affaire.")
        existante = existantes[0] if existantes else None
        if existante and not existante.actif:
            raise serializers.ValidationError(f"L'affaire {num} est archivée : désarchivez-la d'abord.")
        if existante:
            verifier(self.request.user, 'marches_affaires', 'modifier', existante)
        else:
            verifier(self.request.user, 'marches_affaires', 'creer')
        donnees = {
            'num_affaire': num,
            'nom': str(valeurs.get('nom') or '').strip(),
            'responsables': self._personnes(valeurs.get('responsables'), 'responsables'),
            'membres': self._personnes(valeurs.get('membres'), 'membres', accepter_tous=True),
        }
        noms_prestations = separer(valeurs.get('prestations'))
        prestations = {p.nom.lower(): p for p in Prestation.objects.filter(nom__in=noms_prestations)}
        inconnues = [n for n in noms_prestations if n.lower() not in prestations]
        if inconnues:
            raise serializers.ValidationError({'prestations': f"prestation(s) inconnue(s) : {', '.join(inconnues)}"})

        serializer = AffaireSerializer(existante, data=donnees, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        affaire = serializer.save() if existante else serializer.save(cree_par=getattr(self.request.user, 'employe', None))
        for prestation in prestations.values():
            AffairePrestation.objects.get_or_create(affaire=affaire, prestation=prestation)
        return ('modification' if existante else 'creation'), f"{affaire.num_affaire + ' – ' if affaire.num_affaire else ''}{affaire.nom}"

    def get_queryset(self):
        self.queryset = (Affaire.objects.select_related('cree_par')
                         .prefetch_related('responsables', 'membres')
                         .annotate(nb_prestations=Count('liens_prestations', distinct=True)))
        queryset = super().get_queryset()
        if self.request.query_params.get('mes', '').lower() in VRAI:
            moi = getattr(self.request.user, 'employe', None)
            queryset = queryset.filter(Q(responsables=moi) | Q(membres=moi)) if moi else queryset.none()
        elif self.action in ('list', 'exporter') and self.module:
            # Seulement les affaires du périmètre « Voir » (ou « Exporter ») du module
            queryset = queryset.filter(q_droit(self.request.user, self.module, 'voir' if self.action == 'list' else 'exporter'))
        return queryset.distinct()

    @action(detail=True, methods=['post'])
    def membres(self, request, pk=None):
        """Les responsables d'une affaire peuvent en modifier les membres (Mes marchés)."""
        affaire = self.get_object()
        moi = getattr(request.user, 'employe', None)
        from autorisations.droits import peut_sur
        if not (affaire.responsables.filter(pk=getattr(moi, 'pk', None)).exists()
                or peut_sur(request.user, 'marches_affaires', 'modifier', affaire)):
            raise PermissionDenied("Seuls les responsables de l'affaire peuvent modifier ses membres.")
        champ = PersonnesField(many=True, allow_empty=False)
        try:
            membres = champ.to_internal_value(request.data.get('membres', []))
        except serializers.ValidationError as exc:
            raise serializers.ValidationError({'membres': exc.detail})
        affaire.membres.set(membres)
        affaire.save(update_fields=['modifie_le'])
        return Response(self.get_serializer(self.get_queryset().get(pk=affaire.pk)).data)

    @action(detail=True, methods=['post'])
    def supprimer(self, request, pk=None):
        """Suppression définitive (DELETE, lui, archive l'affaire)."""
        affaire = self.get_object()
        raisons = affaire.raisons_non_supprimable()
        if raisons:
            return Response({
                'detail': f"Impossible de supprimer « {affaire.nom} » : elle contient encore {', '.join(raisons)}. "
                          "Décochez d'abord ses prestations (après avoir supprimé leurs projets et descriptions), "
                          "ou archivez-la.",
                'code': 'non_vide',
            }, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            affaire.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def desarchiver(self, request, pk=None):
        affaire = self.get_object()
        affaire.actif = True
        affaire.save(update_fields=['actif', 'modifie_le'])
        return Response(self.get_serializer(affaire).data)

    @action(detail=True, methods=['post'])
    def prestations(self, request, pk=None):
        affaire = self.get_object()
        prestation = Prestation.objects.filter(pk=entier(request.data.get('prestation'))).first()
        if prestation is None:
            return Response({'detail': 'Prestation introuvable.'}, status=status.HTTP_400_BAD_REQUEST)
        projets = Projet.objects.filter(affaire=affaire, prestation=prestation)
        return self.cochage(
            request, AffairePrestation, {'affaire': affaire, 'prestation': prestation},
            message_utilise=f"Impossible de décocher « {prestation.nom} » : elle contient des projets.",
            est_utilise=projets.exists,
        )


class PrestationViewSet(ImportExcelMixin, BaseMarche):
    serializer_class = PrestationSerializer
    search_fields = ['nom', 'unite']
    ordering_fields = BaseMarche.ordering_fields + ['unite']
    verbes_actions = {**BaseMarche.verbes_actions, 'modele': 'voir', 'importer': 'importer', 'exporter': 'exporter'}

    # --- Import Excel -------------------------------------------------------
    import_nom = 'Prestations'
    import_colonnes = [
        ColonneImport('nom', 'Nom prestation', requis=True, aide='Si une prestation porte déjà ce nom, elle est mise à jour ; sinon elle est créée.', exemple='Saisie de fiches', largeur=30),
        ColonneImport('unite', 'Unité', requis=True, exemple='fiches', largeur=14),
        ColonneImport('rendements', 'Rendement objectif', requis=True, multiple=True, nb_dans_modele=3,
                      aide='Un nombre par colonne (rendement objectif par jour). Au moins un. Ajoutez des colonnes « Rendement objectif 4 », « 5 »… si besoin. Les décimales sont acceptées (80,5).',
                      exemple=['120', '80,5'], largeur=20),
    ]
    import_alias = {'valeurs_rendement': 'rendements'}
    import_explications = [
        'Pour une prestation existante, la liste des rendements remplace l’ancienne ; un rendement déjà utilisé par un projet ne peut pas être retiré.',
    ]

    def importer_ligne(self, valeurs):
        nom = str(valeurs.get('nom') or '').strip()
        existante = Prestation.objects.filter(nom__iexact=nom).first() if nom else None
        donnees = {
            'nom': existante.nom if existante else nom,
            'unite': str(valeurs.get('unite') or '').strip(),
            'valeurs_rendement': [str(v) for v in valeurs.get('rendements') or []],
        }
        serializer = PrestationSerializer(existante, data=donnees, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        prestation = serializer.save() if existante else serializer.save(cree_par=getattr(self.request.user, 'employe', None))
        return ('modification' if existante else 'creation'), prestation.nom

    @property
    def ordering(self):
        # Affaire choisie : ses prestations cochées d'abord, puis les autres (ordre du catalogue)
        if entier(self.request.query_params.get('affaire')):
            return ['-cochee', 'ordre', 'id']
        return ['ordre', 'id']

    # Paramètres > Autorisation : « Marchés > Prestations » (catalogue). Lecture : avec « Voir », tout le catalogue ;
    # sinon (Mes marchés, ou cocher pour une affaire) seulement les prestations cochées des affaires où l'on est
    # responsable ou membre, ou dont on peut modifier l'affaire.
    LECTURE = ('list', 'retrieve')

    @property
    def module(self):
        return None if self.action in self.LECTURE else 'marches_prestations'

    def get_queryset(self):
        from autorisations.droits import peut
        queryset = Prestation.objects.select_related('cree_par').prefetch_related('rendements')
        if (self.action in self.LECTURE and not peut(self.request.user, 'marches_prestations', 'voir')
                and not peut(self.request.user, 'marches_affaires', 'modifier')):
            # Mes marchés : les prestations des affaires dont on est responsable ou membre
            moi = getattr(self.request.user, 'employe', None)
            queryset = queryset.filter(Q(liens_affaires__affaire__responsables=moi)
                                       | Q(liens_affaires__affaire__membres=moi)).distinct()
        affaire = entier(self.request.query_params.get('affaire'))
        if affaire:
            queryset = queryset.annotate(
                cochee=Exists(AffairePrestation.objects.filter(affaire_id=affaire, prestation=OuterRef('pk'))),
                nb_projets=Count('projets', filter=Q(projets__affaire_id=affaire), distinct=True),
            )
            if self.request.query_params.get('cochees', '').lower() in VRAI:
                queryset = queryset.filter(cochee=True)
        return queryset


class EcritureSurAffaireMixin:
    """
    Projets / communes et descriptions : modules « Marchés > Projets / Communes » et « Marchés > Descriptions ».
      lecture : les affaires du périmètre « Voir » (ou « Exporter »), et celles dont on est responsable ou membre
                (Mes marchés, en consultation) ;
      créer, modifier, supprimer : ce droit sur l'affaire.
    """
    LECTURE = ('list', 'retrieve', 'exporter')
    MODULE = None
    CHEMIN_AFFAIRE = None   # ex. 'affaire' ou 'projet__affaire'

    @property
    def module(self):
        return None if self.action in self.LECTURE else self.MODULE

    def _verbe_ecriture(self):
        from autorisations.permissions import verbe_de_la_requete
        return verbe_de_la_requete(self.request, self)

    def filtrer_lecture(self, queryset):
        moi = getattr(self.request.user, 'employe', None)
        p = f'{self.CHEMIN_AFFAIRE}__'
        action = 'exporter' if self.action == 'exporter' else 'voir'
        visibles = q_droit(self.request.user, self.MODULE, action, p) | Q(**{f'{p}responsables': moi}) | Q(**{f'{p}membres': moi})
        return queryset.filter(visibles).distinct()

    def get_object(self):
        objet = super().get_object()
        if self.module:
            verifier(self.request.user, self.MODULE, self._verbe_ecriture(), self.affaire_de(objet))
        return objet

    def perform_create(self, serializer):
        affaire = self.affaire_creation(serializer.validated_data)
        if affaire is not None:
            verifier(self.request.user, self.MODULE, 'creer', affaire)
        super().perform_create(serializer)


class ProjetViewSet(EcritureSurAffaireMixin, BaseMarche):
    MODULE = 'marches_projets'
    CHEMIN_AFFAIRE = 'affaire'
    serializer_class = ProjetSerializer

    def affaire_de(self, objet):
        return objet.affaire

    def affaire_creation(self, donnees):
        return donnees.get('affaire')
    filtres = {'affaire': 'affaire_id', 'prestation': 'prestation_id'}
    ordering_fields = BaseMarche.ordering_fields + ['numero', 'date_livraison', 'quantite']

    def get_queryset(self):
        self.queryset = (Projet.objects.select_related('prestation', 'rendement', 'cree_par')
                         .annotate(nb_descriptions=Count('descriptions', distinct=True)))
        queryset = super().get_queryset()
        return self.filtrer_lecture(queryset) if self.action in self.LECTURE else queryset


class TacheViewSet(BaseMarche):
    """Catalogue des tâches : « Marchés > Tâches » (même Voir). Le pointage a sa propre liste."""
    module = 'marches_taches'
    serializer_class = TacheSerializer
    queryset = Tache.objects.select_related('cree_par')


class StatutViewSet(BaseMarche):
    """Catalogue des statuts : « Marchés > Statuts » (même Voir). Les feuilles ont leur propre liste."""
    module = 'marches_statuts'
    serializer_class = StatutSerializer
    queryset = Statut.objects.select_related('cree_par')


class DescriptionViewSet(EcritureSurAffaireMixin, BaseMarche):
    """Descriptions d'un projet : toujours filtrer par ?projet=<id>."""
    MODULE = 'marches_descriptions'
    CHEMIN_AFFAIRE = 'projet__affaire'
    serializer_class = DescriptionSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return self.filtrer_lecture(queryset) if self.action in self.LECTURE else queryset

    def affaire_de(self, objet):
        return objet.projet.affaire

    def affaire_creation(self, donnees):
        projet = donnees.get('projet')
        return projet.affaire if projet else None
    queryset = Description.objects.select_related('projet__prestation', 'cree_par')
    filtres = {'projet': 'projet_id'}
    ordering_fields = BaseMarche.ordering_fields + ['numero', 'quantite']
