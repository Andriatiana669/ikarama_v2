# backend/autorisations/serializers.py
from rest_framework import serializers

from utilisateurs.serializers import EmployeResumeSerializer

from .models import RegleAcces


class RegleAccesSerializer(serializers.ModelSerializer):
    employe_details = EmployeResumeSerializer(source='employe', read_only=True)
    description = serializers.CharField(read_only=True)
    effet_libelle = serializers.CharField(source='get_effet_display', read_only=True)
    critere_libelle = serializers.CharField(source='get_critere_display', read_only=True)
    portee_libelle = serializers.CharField(source='get_portee_display', read_only=True)
    nb_personnes = serializers.SerializerMethodField()

    class Meta:
        model = RegleAcces
        fields = ['id', 'effet', 'effet_libelle', 'critere', 'critere_libelle', 'pole', 'poste',
                  'employe', 'employe_details', 'portee', 'portee_libelle', 'actif', 'commentaire',
                  'description', 'nb_personnes', 'created_at', 'updated_at']

    def get_nb_personnes(self, obj):
        from utilisateurs.models import Employe

        from .acces import q_regle
        return Employe.objects.filter(q_regle(obj)).distinct().count()
