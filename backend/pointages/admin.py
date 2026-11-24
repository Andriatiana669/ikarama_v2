# backend/pointages/admin.py
from django.contrib import admin

from .models import PartPointage, Pointage


class PartInline(admin.TabularInline):
    model = PartPointage
    extra = 0
    raw_id_fields = ['description', 'ligne']
    readonly_fields = ['minutes_normales', 'minutes_hs']


@admin.register(Pointage)
class PointageAdmin(admin.ModelAdmin):
    list_display = ['employe', 'date', 'heure_debut', 'heure_fin', 'tache', 'minutes_normales', 'minutes_hs']
    list_filter = ['date', 'tache']
    search_fields = ['employe__nom', 'employe__code_barre']
    raw_id_fields = ['employe']
    readonly_fields = ['minutes_normales', 'minutes_hs']
    inlines = [PartInline]
