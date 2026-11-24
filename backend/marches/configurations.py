# backend/marches/configurations.py
"""
Paramètres > Configurations Responsables (préfixe /api/marches/configurations-responsables/).
  Lecture : toute personne connectée (pour ajouter une configuration dans le champ Responsables d'une affaire).
  Créer, modifier, supprimer : superadmin.
"""
from rest_framework import serializers, viewsets
from rest_framework.permissions import SAFE_METHODS

from autorisations.acces import q_visible
from autorisations.permissions import AdministrateurUniquement
from utilisateurs.models import Employe
from utilisateurs.serializers import EmployeResumeSerializer

from .models import ConfigurationResponsables


class ConfigurationSerializer(serializers.ModelSerializer):
    personnes = serializers.PrimaryKeyRelatedField(queryset=Employe.objects.all(), many=True, required=False)
    personnes_details = serializers.SerializerMethodField()

    class Meta:
        model = ConfigurationResponsables
        fields = ['id', 'nom', 'personnes', 'personnes_details', 'par_defaut', 'modifie_le']

    def get_personnes_details(self, obj):
        # Seulement les personnes qui ont accès au site
        return EmployeResumeSerializer(obj.personnes.filter(q_visible()).order_by('nom', 'prenom'), many=True).data

    def validate_nom(self, valeur):
        valeur = (valeur or '').strip()
        if not valeur:
            raise serializers.ValidationError('Indiquez un nom.')
        return valeur


class ConfigurationResponsablesViewSet(viewsets.ModelViewSet):
    serializer_class = ConfigurationSerializer
    pagination_class = None
    queryset = ConfigurationResponsables.objects.prefetch_related('personnes')

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return super().get_permissions()
        return [AdministrateurUniquement()]
