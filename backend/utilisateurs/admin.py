# backend/utilisateurs/admin.py
from django.contrib import admin

from .models import Employe, EmployePoste


class EmployePosteInline(admin.TabularInline):
    model = EmployePoste
    extra = 0


@admin.register(Employe)
class EmployeAdmin(admin.ModelAdmin):
    list_display = ['code_barre', 'nom', 'prenom', 'prenom_usuel', 'chef', 'user', 'derniere_synchro']
    search_fields = ['code_barre', 'nom', 'prenom', 'prenom_usuel', 'email']
    list_filter = ['postes__pole']
    raw_id_fields = ['chef', 'user']
    readonly_fields = ['derniere_synchro']
    inlines = [EmployePosteInline]
