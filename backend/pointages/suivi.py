# backend/pointages/suivi.py
"""
Pointages > Suivi et Vérification (superadmins uniquement) : les pointages de toutes les personnes
qui ont accès au site.

  tous/?debut=&fin=&employe=&pole=&affaire=&tache=&search=    liste, modification, suppression
  tous/resume/?debut=&fin=…                                   totaux de la sélection
  verification/?debut=&fin=&employe=&pole=&manques=1          une ligne par personne et jour pointé :
                                                              Heures pointées = H_Durée, Manque = 8 h − H_Durée
                                                              (jours ouvrables ; 0 le week-end)
"""
from django.db.models import Count, Sum
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from autorisations.acces import q_acces
from autorisations.droits import q_droit, verifier
from ikarama.vues import ExportExcelMixin, FiltresMixin
from utilisateurs.models import Employe
from utilisateurs.serializers import EmployeResumeSerializer

from .calculs import MAX_NORMALES, est_ouvrable
from .models import Pointage
from .serializers import PointageSerializer
from .views import periode, supprimer_pointage

FILTRES = {
    'debut': 'date__gte', 'fin': 'date__lte', 'employe': 'employe_id', 'tache': 'tache_id',
    'pole': 'employe__postes__pole', 'affaire': 'parts__description__projet__affaire_id',
}


def pointages_suivis():
    """Pointages des personnes qui ont accès au site."""
    return Pointage.objects.filter(q_acces('employe__'))


class SuiviPointageViewSet(FiltresMixin, ExportExcelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                           mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    module = 'pointages_suivi'
    serializer_class = PointageSerializer
    filtres = FILTRES
    search_fields = ['commentaire', 'tache__nom', 'employe__nom', 'employe__prenom', 'employe__code_barre',
                     'parts__description__nom', 'parts__description__projet__nom',
                     'parts__description__projet__affaire__nom', 'parts__description__projet__affaire__num_affaire']
    ordering_fields = ['date', 'heure_debut', 'employe__nom']
    ordering = ['date', 'employe__nom', 'heure_debut', 'id']
    verbes_actions = {'resume': 'voir', 'exporter': 'exporter'}

    def _action_droit(self):
        from autorisations.permissions import verbe_de_la_requete
        return verbe_de_la_requete(self.request, self)

    def get_queryset(self):
        # Seulement les pointages des personnes du périmètre de l'action (voir, modifier, supprimer, exporter)
        return (pointages_suivis().filter(q_droit(self.request.user, 'pointages_suivi', self._action_droit(), 'employe__'))
                .select_related('employe', 'tache')
                .prefetch_related('parts__description__projet__affaire', 'parts__description__projet__prestation',
                                  'parts__ligne__feuille')
                .distinct())

    def list(self, request, *args, **kwargs):
        if not request.query_params.get('debut') or not request.query_params.get('fin'):
            return Response({'detail': 'Précisez la période (?debut=&fin=).'}, status=status.HTTP_400_BAD_REQUEST)
        return super().list(request, *args, **kwargs)

    def get_object(self):
        # Le pointage est cherché parmi tous les pointages suivis, puis le périmètre de l'action est vérifié
        # (pour répondre « pas le droit » plutôt que « introuvable »)
        pointage = pointages_suivis().filter(pk=self.kwargs['pk']).select_related('employe', 'tache').first()
        if pointage is None:
            from django.http import Http404
            raise Http404
        verifier(self.request.user, 'pointages_suivi', self._action_droit(), pointage.employe)
        return pointage

    def update(self, request, *args, **kwargs):
        """Modification au nom de la personne pointée : ses affaires et ses horaires sont vérifiés."""
        instance = self.get_object()
        serializer = PointageSerializer(instance, data=request.data, partial=kwargs.get('partial', False),
                                        context={**self.get_serializer_context(), 'employe': instance.employe})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        self._prevenir(instance, 'modifié')
        return Response(PointageSerializer(serializer.instance, context=self.get_serializer_context()).data)

    def _prevenir(self, pointage, action_faite):
        """La personne est prévenue quand un administrateur modifie ou supprime un de ses pointages."""
        auteur = getattr(self.request.user, 'employe', None)
        if auteur is None or auteur.pk == pointage.employe_id:
            return
        from notifications.services import notifier
        notifier([pointage.employe_id], 'pointage_modifie',
                 f"Votre pointage du {pointage.date:%d/%m/%Y} a été {action_faite}",
                 message=f"{pointage.heure_debut:%H:%M}–{pointage.heure_fin:%H:%M}, par {auteur.identifiant}.",
                 lien='/pointages/mon-temps')

    def perform_destroy(self, instance):
        self._prevenir(instance, 'supprimé')
        supprimer_pointage(instance)

    @action(detail=False, methods=['get'])
    def resume(self, request):
        pointages = self.filter_queryset(self.get_queryset()).order_by().distinct()
        ids = list(pointages.values_list('pk', flat=True))
        totaux = Pointage.objects.filter(pk__in=ids).aggregate(
            n=Sum('minutes_normales'), h=Sum('minutes_hs'), personnes=Count('employe', distinct=True))
        return Response({
            'nb_lignes': len(ids), 'nb_personnes': totaux['personnes'] or 0,
            'minutes_normales': totaux['n'] or 0, 'minutes_hs': totaux['h'] or 0, 'erreurs': [],
        })


class VerificationViewSet(FiltresMixin, ExportExcelMixin, viewsets.GenericViewSet):
    """Une ligne par personne et par jour pointé, avec le manque par rapport aux 8 h."""
    module = 'pointages_verification'
    verbes_actions = {'exporter': 'exporter'}
    filtres = {k: v for k, v in FILTRES.items() if k in ('debut', 'fin', 'employe', 'pole')}

    def get_queryset(self):
        # Les personnes du périmètre de l'action (voir ou exporter) de Pointages > Vérification
        action = 'exporter' if self.action == 'exporter' else 'voir'
        return pointages_suivis().filter(q_droit(self.request.user, 'pointages_verification', action, 'employe__')).distinct()

    def _lignes(self):
        debut, fin = periode(self.request)
        pointages = self.filter_queryset(self.get_queryset()).filter(date__gte=debut, date__lte=fin).order_by()
        texte = self.request.query_params.get('search', '').strip()
        if texte:   # recherche sur la personne
            from django.db.models import Q
            pointages = pointages.filter(Q(employe__nom__icontains=texte) | Q(employe__prenom__icontains=texte)
                                         | Q(employe__prenom_usuel__icontains=texte) | Q(employe__code_barre__icontains=texte))
        jours = (Pointage.objects.filter(pk__in=pointages.values('pk'))
                 .values('date', 'employe_id').annotate(minutes=Sum('minutes_normales'))
                 .order_by('-date', 'employe__nom', 'employe__prenom'))
        employes = {e.pk: e for e in Employe.objects.filter(pk__in={j['employe_id'] for j in jours})}
        seulement_manques = self.request.query_params.get('manques') in ('1', 'true', 'oui')
        lignes = []
        for j in jours:
            manque = max(0, MAX_NORMALES - j['minutes']) if est_ouvrable(j['date']) else 0
            if seulement_manques and not manque:
                continue
            employe = employes[j['employe_id']]
            lignes.append({
                'id': int(f"{j['date']:%Y%m%d}{employe.pk:07d}"),   # identifiant numérique unique (jour + personne)
                'date': j['date'].isoformat(),
                'employe': EmployeResumeSerializer(employe).data,
                'heures': round(j['minutes'] / 60, 2),
                'manque': round(manque / 60, 2),
                'minutes_pointees': j['minutes'], 'minutes_manque': manque,
            })
        return lignes

    def list(self, request):
        lignes = self._lignes()
        page = self.paginate_queryset(lignes)
        return self.get_paginated_response(page) if page is not None else Response(lignes)

    def lignes_export(self):
        return self._lignes()
