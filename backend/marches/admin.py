# backend/marches/admin.py
from django.contrib import admin

from .models import Affaire, AffairePrestation, Description, Prestation, Projet, RendementObjectif, Statut, Tache


class RendementInline(admin.TabularInline):
    model = RendementObjectif
    extra = 0
    fields = ['valeur']


class AffairePrestationInline(admin.TabularInline):
    model = AffairePrestation
    extra = 0
    fields = ['prestation']


@admin.register(Prestation)
class PrestationAdmin(admin.ModelAdmin):
    list_display = ['nom', 'unite', 'ordre', 'cree_le']
    search_fields = ['nom']
    inlines = [RendementInline]


@admin.register(Affaire)
class AffaireAdmin(admin.ModelAdmin):
    list_display = ['id', 'num_affaire', 'nom', 'actif', 'cree_par', 'cree_le']
    list_filter = ['actif']
    search_fields = ['nom', 'num_affaire']
    filter_horizontal = ['responsables', 'membres']
    inlines = [AffairePrestationInline]


@admin.register(Projet)
class ProjetAdmin(admin.ModelAdmin):
    list_display = ['affaire', 'numero', 'nom', 'prestation', 'quantite', 'date_livraison']
    list_filter = ['prestation']
    search_fields = ['nom', 'affaire__nom']


admin.site.register(Tache)


@admin.register(Statut)
class StatutAdmin(admin.ModelAdmin):
    list_display = ['nom', 'couleur', 'ordre']


@admin.register(Description)
class DescriptionAdmin(admin.ModelAdmin):
    list_display = ['projet', 'numero', 'nom', 'quantite']
    search_fields = ['nom', 'projet__nom']
