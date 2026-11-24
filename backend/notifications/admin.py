from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['destinataire', 'type', 'titre', 'lu', 'envoyee_par_email', 'cree_le']
    list_filter = ['type', 'lu', 'envoyee_par_email']
    raw_id_fields = ['destinataire']
