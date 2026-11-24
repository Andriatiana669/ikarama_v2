# backend/rendements/admin.py
from django.contrib import admin

from .models import ParametresRendement


@admin.register(ParametresRendement)
class ParametresRendementAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'heures_par_jour', 'note_objectif', 'note_max', 'modifie_le']

    def has_add_permission(self, request):
        return not ParametresRendement.objects.exists()
