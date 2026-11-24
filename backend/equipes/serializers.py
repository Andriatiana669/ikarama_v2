# backend/equipes/serializers.py
from rest_framework import serializers

from utilisateurs.models import Employe
from utilisateurs.serializers import EmployeResumeSerializer, EmployeSerializer


def premier_poste(employe):
    postes = list(employe.postes.all())   # profite du prefetch_related
    return postes[0] if postes else None


class EquipeSerializer(serializers.ModelSerializer):
    """
    Une équipe est identifiée par son responsable : id de l'équipe = id du responsable.
    """
    responsable = serializers.SerializerMethodField()
    pole = serializers.SerializerMethodField()
    poste = serializers.SerializerMethodField()
    nb_membres = serializers.IntegerField(read_only=True)

    class Meta:
        model = Employe
        fields = ['id', 'responsable', 'pole', 'poste', 'nb_membres']

    def get_responsable(self, obj):
        return EmployeResumeSerializer(obj).data

    def get_pole(self, obj):
        poste = premier_poste(obj)
        return poste.pole if poste else None

    def get_poste(self, obj):
        poste = premier_poste(obj)
        return poste.poste_nom if poste else None


class EquipeDetailSerializer(EquipeSerializer):
    membres = serializers.SerializerMethodField()

    class Meta(EquipeSerializer.Meta):
        fields = EquipeSerializer.Meta.fields + ['membres']

    def get_membres(self, obj):
        from django.db.models import Count

        from autorisations.acces import filtre_ou_rien, q_visible
        membres = (obj.subordonnes.filter(q_visible()).prefetch_related('postes').select_related('chef')
                   .annotate(nb_subordonnes=Count('subordonnes', filter=filtre_ou_rien('subordonnes__'), distinct=True))
                   .order_by('nom', 'prenom'))
        return EmployeSerializer(membres, many=True).data
