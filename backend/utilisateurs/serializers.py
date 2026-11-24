# backend/utilisateurs/serializers.py
from rest_framework import serializers

from .models import Employe, EmployePoste


class EmployeResumeSerializer(serializers.ModelSerializer):
    """Version courte d'un employé : listes déroulantes, références dans d'autres objets."""
    nom_affiche = serializers.CharField(read_only=True)
    identifiant = serializers.CharField(read_only=True)

    class Meta:
        model = Employe
        fields = ['id', 'code_barre', 'nom', 'prenom', 'prenom_usuel', 'nom_affiche', 'identifiant']


class EmployePosteSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployePoste
        fields = ['id', 'pole_id', 'pole', 'poste_nom', 'poste_statut']


class EmployeSerializer(serializers.ModelSerializer):
    """Fiche complète (lecture seule : les données viennent de l'API RH)."""
    nom_affiche = serializers.CharField(read_only=True)
    identifiant = serializers.CharField(read_only=True)
    postes = EmployePosteSerializer(many=True, read_only=True)
    chef = serializers.SerializerMethodField()
    nb_subordonnes = serializers.IntegerField(read_only=True, required=False)
    a_un_compte = serializers.SerializerMethodField()
    # CONNECTE | AUTORISE (jamais connecté) | RETIRE (accès retiré)
    statut_acces = serializers.SerializerMethodField()

    class Meta:
        model = Employe
        fields = [
            'id', 'external_id', 'code_barre', 'civilite', 'nom', 'prenom', 'prenom_usuel',
            'nom_affiche', 'identifiant', 'email', 'chef', 'postes', 'nb_subordonnes', 'a_un_compte', 'statut_acces',
            'derniere_synchro',
        ]
        read_only_fields = fields

    def get_chef(self, obj):
        """Le N+1 n'est affiché que s'il est lui-même visible (règles d'accès au site)."""
        from autorisations.acces import est_visible
        return EmployeResumeSerializer(obj.chef).data if est_visible(obj.chef) else None

    def get_a_un_compte(self, obj):
        return obj.user_id is not None

    def get_statut_acces(self, obj):
        from autorisations.acces import statut
        return statut(obj)
