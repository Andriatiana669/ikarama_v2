# backend/autorisations/admin.py
# Accès de secours : si une règle bloque tout le monde (superadmins compris), un compte créé par
# `createsuperuser` peut se connecter à /admin/ avec son mot de passe et corriger les règles ici.
from django.contrib import admin

from .acces import invalider
from .models import RegleAcces


@admin.register(RegleAcces)
class RegleAccesAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'effet', 'critere', 'actif', 'commentaire', 'updated_at']
    list_filter = ['effet', 'critere', 'actif']
    list_editable = ['actif']
    search_fields = ['pole', 'poste', 'employe__code_barre', 'employe__nom', 'commentaire']
    raw_id_fields = ['employe']
    readonly_fields = ['cree_par', 'created_at', 'updated_at']
    actions = ['desactiver']

    @admin.action(description='Désactiver les règles sélectionnées')
    def desactiver(self, request, queryset):
        queryset.update(actif=False)
        invalider()


from .models import AttributionRole, DroitRole, JournalAutorisation, Role  # noqa: E402


class DroitRoleEnLigne(admin.TabularInline):
    model = DroitRole
    extra = 0
    raw_id_fields = ['employe', 'affaire']


class AttributionRoleEnLigne(admin.TabularInline):
    model = AttributionRole
    extra = 0
    raw_id_fields = ['employe']


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Secours : Paramètres > Autorisation se gère normalement dans l'application."""
    list_display = ['nom', 'actif', 'updated_at']
    inlines = [DroitRoleEnLigne, AttributionRoleEnLigne]


@admin.register(JournalAutorisation)
class JournalAutorisationAdmin(admin.ModelAdmin):
    list_display = ['date', 'auteur', 'texte']
    readonly_fields = ['date', 'auteur', 'texte']
