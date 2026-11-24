# backend/gsheets/admin.py
from django.contrib import admin

from .models import CritereControle, Feuille, LigneFeuille, PerimetreFeuille


class PerimetreInline(admin.TabularInline):
    model = PerimetreFeuille
    extra = 0


class CritereInline(admin.TabularInline):
    model = CritereControle
    extra = 0


@admin.register(Feuille)
class FeuilleAdmin(admin.ModelAdmin):
    list_display = ['nom', 'cree_par', 'cree_le']
    search_fields = ['nom']
    inlines = [PerimetreInline, CritereInline]


@admin.register(LigneFeuille)
class LigneAdmin(admin.ModelAdmin):
    list_display = ['feuille', 'numero', 'description', 'employe', 'statut', 'avancement']
    list_filter = ['feuille']
    raw_id_fields = ['description', 'employe', 'controleur', 'employe_reprise']
