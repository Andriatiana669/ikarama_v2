# backend/notifications/views.py
"""
API des notifications (préfixe /api/notifications/) — les miennes seulement.
  GET  /                    liste (non lues d'abord)       GET /compte/      nombre de non lues
  POST /<id>/lire/          marquer comme lue              POST /tout-lire/  tout marquer comme lu
"""
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'type', 'titre', 'message', 'lien', 'lu', 'cree_le']


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        employe = getattr(self.request.user, 'employe', None)
        return Notification.objects.filter(destinataire=employe).order_by('lu', '-cree_le', '-id')

    @action(detail=False, methods=['get'])
    def compte(self, request):
        return Response({'non_lues': self.get_queryset().filter(lu=False).count()})

    @action(detail=True, methods=['post'])
    def lire(self, request, pk=None):
        self.get_queryset().filter(pk=pk).update(lu=True)
        return Response({'non_lues': self.get_queryset().filter(lu=False).count()})

    @action(detail=False, methods=['post'], url_path='tout-lire')
    def tout_lire(self, request):
        self.get_queryset().filter(lu=False).update(lu=True)
        return Response({'non_lues': 0})
