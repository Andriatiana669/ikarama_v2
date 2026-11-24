# backend/utilisateurs/views.py
from django.db.models import Count, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from autorisations.acces import filtre_ou_rien, q_visible
from autorisations.permissions import AdministrateurUniquement
from ikarama.vues import FiltresMixin

from .models import Employe, EmployePoste
from .serializers import EmployeResumeSerializer, EmployeSerializer
from .services_rh import ApiRhIndisponible, synchroniser_tous


class EmployeViewSet(FiltresMixin, viewsets.ReadOnlyModelViewSet):
    """
    GET  /api/utilisateurs/                      liste (paginée)
         ?search=dupont   ?pole=INFO   ?poste=...   ?statut=...   ?chef=<id>
         ?format_court=true  (id, matricule, noms seulement : listes déroulantes)
    GET  /api/utilisateurs/<id>/                 fiche
    GET  /api/utilisateurs/<id>/subordonnes/     ?niveau=direct|hierarchie
    GET  /api/utilisateurs/valeurs-filtres/      pôles, postes, statuts (pour les filtres)
    POST /api/utilisateurs/synchroniser/         synchro complète API RH (administrateurs)
    """
    module = 'utilisateurs'
    serializer_class = EmployeSerializer
    search_fields = ['code_barre', 'nom', 'prenom', 'prenom_usuel', 'email']
    ordering_fields = ['nom', 'prenom', 'code_barre']
    ordering = ['nom', 'prenom']
    filtres = {
        'pole': 'postes__pole',
        'poste': 'postes__poste_nom',
        'statut': 'postes__poste_statut',
        'chef': 'chef_id',
    }

    def get_queryset(self):
        # Seules les personnes visibles (accès au site, ou déjà connectées une fois)
        queryset = (
            Employe.objects.filter(q_visible()).select_related('chef')
            .prefetch_related('postes')
            .annotate(nb_subordonnes=Count('subordonnes', filter=filtre_ou_rien('subordonnes__'), distinct=True))
        )
        return queryset.distinct()

    def get_serializer_class(self):
        if self.request.query_params.get('format_court', '').lower() == 'true':
            return EmployeResumeSerializer
        return EmployeSerializer

    @action(detail=True, methods=['get'])
    def subordonnes(self, request, pk=None):
        employe = self.get_object()
        if request.query_params.get('niveau') == 'hierarchie':
            ids = [e.pk for e in employe.subordonnes_hierarchie()]
            liste = list(Employe.objects.filter(pk__in=ids).filter(q_visible()).order_by('nom', 'prenom'))
        else:
            liste = list(employe.subordonnes.filter(q_visible()).order_by('nom', 'prenom'))
        return Response(EmployeResumeSerializer(liste, many=True).data)

    @action(detail=False, methods=['get'], url_path='valeurs-filtres')
    def valeurs_filtres(self, request):
        def distincts(champ):
            return list(
                EmployePoste.objects.filter(q_visible('employe__'))
                .exclude(Q(**{f'{champ}__isnull': True}) | Q(**{champ: ''}))
                .values_list(champ, flat=True).distinct().order_by(champ)
            )
        return Response({
            'poles': distincts('pole'),
            'postes': distincts('poste_nom'),
            'statuts': distincts('poste_statut'),
        })

    @action(detail=False, methods=['post'], permission_classes=[AdministrateurUniquement])
    def synchroniser(self, request):
        entete = request.headers.get('Authorization', '')
        jeton = entete.split(' ', 1)[1] if entete.startswith('Bearer ') else None
        try:
            resume = synchroniser_tous(jeton)
        except ApiRhIndisponible as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(resume)
