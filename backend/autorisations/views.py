# backend/autorisations/views.py
"""
Paramètres > Accès au site (administrateurs uniquement). Préfixe /api/autorisations/.

  regles/                 CRUD des règles   (?confirmer=1 pour accepter de perdre son propre accès)
  acces/apercu/           mode (ouvert / restreint), nombre de personnes autorisées
  acces/verifier/?employe=<id>   la personne a-t-elle accès, et selon quelles règles
  acces/employes/?search= recherche parmi TOUS les employés (y compris sans accès)
  acces/valeurs/          tous les pôles et postes connus (pour les listes déroulantes)
"""
from django.db import transaction
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from utilisateurs.models import Employe, EmployePoste
from utilisateurs.serializers import EmployeResumeSerializer

from . import acces
from .models import RegleAcces
from .permissions import AdministrateurUniquement
from .serializers import RegleAccesSerializer


class PerteDeSonAcces(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = ("Avec cette modification, vous n'auriez plus accès à Ikarama, "
                      "y compris à cette page. Confirmez-vous ?")
    default_code = 'perte_acces'


class RegleAccesViewSet(viewsets.ModelViewSet):
    module = 'autorisations'
    permission_classes = [AdministrateurUniquement]
    serializer_class = RegleAccesSerializer
    queryset = RegleAcces.objects.select_related('employe')
    search_fields = ['pole', 'poste', 'commentaire', 'employe__code_barre', 'employe__nom', 'employe__prenom']
    ordering_fields = ['effet', 'critere', 'created_at']

    def _avec_controle(self, operation):
        """
        Exécute la modification, puis vérifie que l'administrateur garde son accès.
        Sinon tout est annulé, sauf si la requête contient ?confirmer=1.
        """
        moi = getattr(self.request.user, 'employe', None)
        try:
            with transaction.atomic():   # une exception annule toute la modification
                resultat = operation()
                acces.invalider()
                if not acces.a_acces(moi) and self.request.query_params.get('confirmer') != '1':
                    raise PerteDeSonAcces()
        except PerteDeSonAcces:
            acces.invalider()
            raise
        return resultat

    def perform_create(self, serializer):
        self._avec_controle(lambda: serializer.save(cree_par=getattr(self.request.user, 'employe', None)))

    def perform_update(self, serializer):
        self._avec_controle(serializer.save)

    def perform_destroy(self, instance):
        self._avec_controle(instance.delete)


class AccesViewSet(viewsets.ViewSet):
    module = 'autorisations'
    permission_classes = [AdministrateurUniquement]

    @action(detail=False, methods=['get'])
    def apercu(self, request):
        etat = acces.etat()
        total = Employe.objects.count()
        nb = total - len(etat['refuses']) if etat['ouvert'] else len(etat['autorises'])
        moi = getattr(request.user, 'employe', None)
        return Response({
            'mode_ouvert': etat['ouvert'],
            'nb_autorises': nb,
            'nb_employes': total,
            'nb_regles_actives': RegleAcces.objects.filter(actif=True).count(),
            'moi': acces.expliquer(moi) if moi else None,
        })

    @action(detail=False, methods=['get'])
    def verifier(self, request):
        employe = Employe.objects.filter(pk=request.query_params.get('employe')).first()
        if employe is None:
            return Response({'detail': 'Employé introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({**acces.expliquer(employe), 'employe': EmployeResumeSerializer(employe).data,
                         'statut': acces.statut(employe)})

    @action(detail=False, methods=['get'])
    def employes(self, request):
        """Recherche dans TOUS les employés : on doit pouvoir donner accès à quelqu'un qui ne l'a pas encore."""
        texte = request.query_params.get('search', '').strip()
        employes = Employe.objects.all()
        if texte:
            employes = employes.filter(Q(code_barre__icontains=texte) | Q(nom__icontains=texte)
                                       | Q(prenom__icontains=texte) | Q(prenom_usuel__icontains=texte))
        return Response(EmployeResumeSerializer(employes.order_by('nom', 'prenom')[:20], many=True).data)

    @action(detail=False, methods=['get'])
    def valeurs(self, request):
        def distincts(champ):
            return list(EmployePoste.objects.exclude(Q(**{f'{champ}__isnull': True}) | Q(**{champ: ''}))
                        .values_list(champ, flat=True).distinct().order_by(champ))
        return Response({'poles': distincts('pole'), 'postes': distincts('poste_nom')})
