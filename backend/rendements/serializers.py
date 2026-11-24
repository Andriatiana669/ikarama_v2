# backend/rendements/serializers.py
from rest_framework import serializers

from .models import ParametresRendement


class TrancheSerializer(serializers.Serializer):
    jusqua = serializers.DecimalField(max_digits=6, decimal_places=2, allow_null=True)
    note = serializers.DecimalField(max_digits=4, decimal_places=2)


class ParametresRendementSerializer(serializers.ModelSerializer):
    tranches_reprise = TrancheSerializer(many=True)

    class Meta:
        model = ParametresRendement
        fields = ['heures_par_jour', 'note_objectif', 'note_max', 'note_critere_min', 'note_critere_max',
                  'tranches_reprise', 'modifie_le']

    def to_internal_value(self, donnees):
        valeurs = super().to_internal_value(donnees)
        if 'tranches_reprise' in valeurs:   # stocké en JSON : nombres simples
            valeurs['tranches_reprise'] = [
                {'jusqua': float(t['jusqua']) if t['jusqua'] is not None else None, 'note': float(t['note'])}
                for t in valeurs['tranches_reprise']
            ]
        return valeurs
