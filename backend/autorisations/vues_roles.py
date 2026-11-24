# backend/autorisations/vues_roles.py
"""
API de Paramètres > Autorisation (superadmins) — préfixe /api/autorisations/
  GET  catalogue/                     modules, actions, périmètres, droits de base de chaque case
  CRUD roles/                         rôles ; PUT roles/<id>/droits/ remplace toute la grille d'un rôle
  CRUD attributions/?role=<id>        qui a le rôle (personne, poste, pôle)
  GET  roles/<id>/personnes/          les personnes qui ont ce rôle (attributions comprises)
  POST tester/                        « Tester un accès » : personne + module + action (+ cible) -> réponse et raisons
  GET  journal/                       qui a changé quoi
"""
from types import SimpleNamespace

from django.db import transaction
from django.db.models import Count, Q
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from utilisateurs.models import Employe
from utilisateurs.serializers import EmployeResumeSerializer

from .acces import q_visible
from .droits import ACTIONS, MODULES, PERIMETRES, base_de, expliquer, roles_de
from .models import AttributionRole, DroitRole, JournalAutorisation, Role
from .permissions import AdministrateurUniquement


def journaliser(request, texte):
    JournalAutorisation.objects.create(auteur=getattr(request.user, 'employe', None), texte=texte[:500])


def libelle_droit(d):
    module = MODULES.get(d['module'], {})
    perimetres = PERIMETRES.get(module.get('cible'), {})
    return (f"{'Refuser' if d['effet'] == 'REFUSER' else 'Autoriser'} « {ACTIONS.get(d['action'], d['action'])} » "
            f"sur {module.get('libelle', d['module'])} : {perimetres.get(d['perimetre'], d['perimetre'])}")


class CatalogueView(APIView):
    permission_classes = [AdministrateurUniquement]

    def get(self, request):
        return Response({
            'actions': ACTIONS,
            'modules': [{
                'code': code, 'libelle': m['libelle'], 'aide': m['aide'], 'cible': m['cible'], 'actions': m['actions'],
                'perimetres': PERIMETRES[m['cible']],
                'base': {a: base_de(code, a) for a in m['actions']},
            } for code, m in MODULES.items()],
        })


class DroitSerializer(serializers.ModelSerializer):
    employe_details = EmployeResumeSerializer(source='employe', read_only=True)
    affaire_nom = serializers.CharField(source='affaire.nom', read_only=True, default=None)

    class Meta:
        model = DroitRole
        fields = ['id', 'effet', 'module', 'action', 'perimetre', 'valeur', 'employe', 'employe_details', 'affaire', 'affaire_nom']

    def validate(self, donnees):
        module = MODULES.get(donnees.get('module'))
        if module is None:
            raise serializers.ValidationError({'module': 'Module inconnu.'})
        if donnees.get('action') not in module['actions']:
            raise serializers.ValidationError({'action': f"Action impossible sur {module['libelle']}."})
        perimetre = donnees.get('perimetre')
        if perimetre not in PERIMETRES[module['cible']]:
            raise serializers.ValidationError({'perimetre': 'Périmètre impossible pour ce module.'})
        if perimetre in ('PERSONNE', 'EQUIPE_DE') and not donnees.get('employe'):
            raise serializers.ValidationError({'employe': 'Choisissez la personne.'})
        if perimetre == 'AFFAIRE' and not donnees.get('affaire'):
            raise serializers.ValidationError({'affaire': 'Choisissez l’affaire.'})
        if perimetre == 'POSTE' and not str(donnees.get('valeur') or '').strip():
            raise serializers.ValidationError({'valeur': 'Indiquez le poste.'})
        if perimetre not in ('PERSONNE', 'EQUIPE_DE'):
            donnees['employe'] = None
        if perimetre != 'AFFAIRE':
            donnees['affaire'] = None
        if perimetre not in ('POLE', 'POSTE'):
            donnees['valeur'] = ''
        return donnees


class RoleSerializer(serializers.ModelSerializer):
    nb_droits = serializers.IntegerField(read_only=True, default=0)
    nb_attributions = serializers.IntegerField(read_only=True, default=0)
    droits = DroitSerializer(many=True, read_only=True)

    class Meta:
        model = Role
        fields = ['id', 'nom', 'description', 'actif', 'nb_droits', 'nb_attributions', 'droits', 'created_at', 'updated_at']


class RoleViewSet(viewsets.ModelViewSet):
    permission_classes = [AdministrateurUniquement]
    serializer_class = RoleSerializer
    search_fields = ['nom', 'description']

    def get_queryset(self):
        return (Role.objects.annotate(nb_droits=Count('droits', distinct=True),
                                      nb_attributions=Count('attributions', filter=Q(attributions__actif=True), distinct=True))
                .prefetch_related('droits__employe', 'droits__affaire').order_by('nom'))

    def perform_create(self, serializer):
        role = serializer.save(cree_par=getattr(self.request.user, 'employe', None))
        journaliser(self.request, f"Rôle « {role.nom} » créé")

    def perform_update(self, serializer):
        avant = serializer.instance.nom
        role = serializer.save()
        journaliser(self.request, f"Rôle « {avant} » modifié" + (f" (renommé « {role.nom} »)" if role.nom != avant else '')
                    + ('' if role.actif else ' — désactivé'))

    def perform_destroy(self, instance):
        journaliser(self.request, f"Rôle « {instance.nom} » supprimé")
        instance.delete()

    @action(detail=True, methods=['put'])
    def droits(self, request, pk=None):
        """Remplace toute la grille du rôle (une seule opération : tout ou rien)."""
        role = self.get_object()
        serializer = DroitSerializer(data=request.data.get('droits', []), many=True)
        serializer.is_valid(raise_exception=True)
        avant = {libelle_droit(d) for d in DroitSerializer(role.droits.all(), many=True).data}
        with transaction.atomic():
            role.droits.all().delete()
            for d in serializer.validated_data:
                DroitRole.objects.create(role=role, **d)
            role.save(update_fields=['updated_at'])
        apres = {libelle_droit(d) for d in DroitSerializer(role.droits.all(), many=True).data}
        changements = [f'+ {x}' for x in sorted(apres - avant)] + [f'− {x}' for x in sorted(avant - apres)]
        if changements:
            journaliser(request, f"Droits du rôle « {role.nom} » : " + ' ; '.join(changements))
        return Response(self.get_serializer(self.get_queryset().get(pk=role.pk)).data)

    @action(detail=True, methods=['get'])
    def personnes(self, request, pk=None):
        """Les personnes (ayant accès au site) qui ont ce rôle, par attribution directe, poste ou pôle."""
        role = self.get_object()
        q = Q(pk__in=[])
        for a in role.attributions.filter(actif=True):
            if a.critere == 'MATRICULE':
                q |= Q(pk=a.employe_id)
            elif a.critere == 'POSTE':
                q |= Q(postes__poste_nom__iexact=a.poste)
            else:
                q |= Q(postes__pole__iexact=a.pole)
        personnes = Employe.objects.filter(q_visible()).filter(q).distinct().order_by('nom', 'prenom')
        return Response({'nombre': personnes.count(), 'personnes': EmployeResumeSerializer(personnes[:200], many=True).data})


class AttributionSerializer(serializers.ModelSerializer):
    employe_details = EmployeResumeSerializer(source='employe', read_only=True)
    description = serializers.CharField(read_only=True)

    class Meta:
        model = AttributionRole
        fields = ['id', 'role', 'critere', 'employe', 'employe_details', 'poste', 'pole', 'actif', 'description']

    def validate(self, donnees):
        critere = donnees.get('critere', getattr(self.instance, 'critere', None))
        if critere == 'MATRICULE' and not donnees.get('employe', getattr(self.instance, 'employe', None)):
            raise serializers.ValidationError({'employe': 'Choisissez la personne.'})
        if critere == 'POSTE' and not str(donnees.get('poste', getattr(self.instance, 'poste', '')) or '').strip():
            raise serializers.ValidationError({'poste': 'Indiquez le poste.'})
        if critere == 'POLE' and not str(donnees.get('pole', getattr(self.instance, 'pole', '')) or '').strip():
            raise serializers.ValidationError({'pole': 'Indiquez le pôle.'})
        return donnees


class AttributionViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin,
                         mixins.DestroyModelMixin, viewsets.GenericViewSet):
    permission_classes = [AdministrateurUniquement]
    serializer_class = AttributionSerializer
    pagination_class = None

    def get_queryset(self):
        attributions = AttributionRole.objects.select_related('employe', 'role')
        role = self.request.query_params.get('role')
        return attributions.filter(role_id=role) if role else attributions

    def perform_create(self, serializer):
        a = serializer.save()
        journaliser(self.request, f"Rôle « {a.role.nom} » attribué à {a.description()}")

    def perform_update(self, serializer):
        a = serializer.save()
        journaliser(self.request, f"Attribution du rôle « {a.role.nom} » à {a.description()} {'activée' if a.actif else 'désactivée'}")

    def perform_destroy(self, instance):
        journaliser(self.request, f"Rôle « {instance.role.nom} » retiré à {instance.description()}")
        instance.delete()


class TesterAccesView(APIView):
    """« Tester un accès » : la décision du moteur pour une personne (avec ses rôles du moment)."""
    permission_classes = [AdministrateurUniquement]

    def post(self, request):
        from marches.models import Affaire
        employe = Employe.objects.filter(pk=request.data.get('employe')).first()
        module, action_ = request.data.get('module'), request.data.get('action')
        if employe is None or module not in MODULES or action_ not in MODULES[module]['actions']:
            return Response({'detail': 'Choisissez une personne, un module et une action de ce module.'}, status=status.HTTP_400_BAD_REQUEST)
        compte = getattr(employe, 'user', None)
        utilisateur = SimpleNamespace(
            is_authenticated=True, employe=employe,
            is_superuser=bool(compte and compte.is_superuser), is_staff=bool(compte and compte.is_staff))
        cible = None
        if request.data.get('cible_employe'):
            cible = Employe.objects.filter(pk=request.data['cible_employe']).first()
        elif request.data.get('cible_affaire'):
            cible = Affaire.objects.filter(pk=request.data['cible_affaire']).first()
        resultat = expliquer(utilisateur, module, action_, cible)
        resultat['roles'] = [r.nom for r in roles_de(employe)]
        return Response(resultat)


class ValeursView(APIView):
    """Postes et pôles connus (API RH), pour les choisir dans une liste avec recherche."""
    permission_classes = [AdministrateurUniquement]

    def get(self, request):
        from utilisateurs.models import EmployePoste
        postes = EmployePoste.objects.exclude(poste_nom__isnull=True).exclude(poste_nom='')
        poles = EmployePoste.objects.exclude(pole__isnull=True).exclude(pole='')
        return Response({
            'postes': sorted(set(postes.values_list('poste_nom', flat=True)), key=str.lower),
            'poles': sorted(set(poles.values_list('pole', flat=True)), key=str.lower),
        })


class JournalView(APIView):
    permission_classes = [AdministrateurUniquement]

    def get(self, request):
        lignes = JournalAutorisation.objects.select_related('auteur')[:200]
        return Response([{'date': l.date, 'auteur': l.auteur.identifiant if l.auteur else '—', 'texte': l.texte} for l in lignes])
