from django.contrib import admin

from .models import AffectationPlanning


@admin.register(AffectationPlanning)
class AffectationPlanningAdmin(admin.ModelAdmin):
    list_display = ['date', 'employe', 'projet', 'cree_par']
    list_filter = ['date']
    raw_id_fields = ['employe', 'projet', 'cree_par']
