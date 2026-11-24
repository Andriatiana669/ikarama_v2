# backend/equipes/views.py
"""
API des équipes (préfixe /api/equipes/), en lecture seule.

  GET /api/equipes/                 équipes (une par responsable)  ?search= ?pole=
  GET /api/equipes/<id>/            une équipe et ses membres (id = id du responsable)
  GET /api/equipes/mes-equipes/     mon équipe (si je suis responsable) + celle de mon N+1
  GET /api/equipes/poles/           pôles, avec nombre d'employés et d'équipes
  GET /api/equipes/organigramme/    hiérarchie complète                  ?pole=
"""
from django.db.models import Count
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from autorisations.acces import filtre_ou_rien, q_visible, responsable_visible
from ikarama.vues import FiltresMixin
from utilisateurs.models import Employe, EmployePoste

from .serializers import EquipeDetailSerializer, EquipeSerializer, premier_poste


def equipes_queryset():
    """
    Les employés visibles qui ont au moins un collaborateur direct visible, avec la taille de leur équipe.
    (Visible = a accès au site, ou s'est déjà connecté : voir autorisations/acces.py.)
    """
    return (Employe.objects.filter(q_visible())
            .annotate(nb_membres=Count('subordonnes', filter=filtre_ou_rien('subordonnes__'), distinct=True))
            .filter(nb_membres__gt=0)
            .prefetch_related('postes'))


class EquipeViewSet(FiltresMixin, viewsets.ReadOnlyModelViewSet):
    module = 'equipes'
    search_fields = ['code_barre', 'nom', 'prenom', 'prenom_usuel']
    ordering_fields = ['nom', 'code_barre', 'nb_membres']
    ordering = ['nom', 'prenom']
    filtres = {'pole': 'postes__pole'}

    def get_queryset(self):
        return equipes_queryset().distinct()

    def get_serializer_class(self):
        return EquipeDetailSerializer if self.action == 'retrieve' else EquipeSerializer

    @action(detail=False, methods=['get'], url_path='mes-equipes')
    def mes_equipes(self, request):
        moi = getattr(request.user, 'employe', None)
        if moi is None:
            return Response([])
        resultat = []
        mienne = equipes_queryset().filter(pk=moi.pk).first()
        if mienne:
            resultat.append({**EquipeSerializer(mienne).data, 'mon_role': 'RESPONSABLE'})
        if moi.chef_id:
            celle_du_chef = equipes_queryset().filter(pk=moi.chef_id).first()
            if celle_du_chef:
                resultat.append({**EquipeSerializer(celle_du_chef).data, 'mon_role': 'MEMBRE'})
        return Response(resultat)

    @action(detail=False, methods=['get'])
    def poles(self, request):
        employes = dict(
            EmployePoste.objects.filter(q_visible('employe__')).exclude(pole__isnull=True).exclude(pole='')
            .values_list('pole').annotate(n=Count('employe', distinct=True))
        )
        equipes = dict(
            EmployePoste.objects.filter(employe__in=equipes_queryset().values('pk'))
            .exclude(pole__isnull=True).exclude(pole='')
            .values_list('pole').annotate(n=Count('employe', distinct=True))
        )
        return Response([
            {'pole': pole, 'nb_employes': nb, 'nb_equipes': equipes.get(pole, 0)}
            for pole, nb in sorted(employes.items(), key=lambda e: e[0].lower())
        ])

    @action(detail=False, methods=['get'])
    def organigramme(self, request):
        """
        Arbre de la hiérarchie : chaque nœud contient ses collaborateurs directs dans « enfants ».
        Racines : les personnes sans responsable (ou dont le responsable est hors du périmètre).
        """
        employes = Employe.objects.filter(q_visible()).prefetch_related('postes').order_by('nom', 'prenom')
        pole = request.query_params.get('pole')
        if pole:
            employes = employes.filter(postes__pole=pole).distinct()

        noeuds = {}
        for e in employes:
            poste = premier_poste(e)
            noeuds[e.id] = {
                'id': e.id, 'chef_id': e.chef_id, 'nom_affiche': e.nom_affiche, 'nom': e.nom,
                'prenom': e.prenom, 'prenom_usuel': e.prenom_usuel, 'code_barre': e.code_barre,
                'identifiant': e.identifiant,
                'poste': poste.poste_nom if poste else None, 'pole': poste.pole if poste else None,
                'enfants': [],
            }

        # Une personne dont le N+1 est masqué (ou hors du pôle) est rattachée
        # au premier responsable visible au-dessus d'elle.
        chefs = dict(Employe.objects.values_list('pk', 'chef_id'))
        for noeud in noeuds.values():
            if noeud['chef_id'] not in noeuds:
                noeud['chef_id'] = responsable_visible(noeud['id'], chefs, noeuds.keys())

        racines = []
        for noeud in noeuds.values():
            parent = noeuds.get(noeud['chef_id'])
            if parent and parent is not noeud:
                parent['enfants'].append(noeud)
            else:
                racines.append(noeud)

        # Protection contre une boucle dans les données RH (A chef de B, B chef de A) :
        # une personne jamais atteinte depuis une racine devient racine, et le lien qui
        # referme la boucle est coupé (sinon l'arbre serait infini).
        atteints = set()

        def parcourir(depart):
            pile = [depart]
            while pile:
                n = pile.pop()
                if n['id'] not in atteints:
                    atteints.add(n['id'])
                    pile.extend(n['enfants'])

        for racine in racines:
            parcourir(racine)
        for noeud in noeuds.values():
            if noeud['id'] not in atteints:
                parent = noeuds.get(noeud['chef_id'])
                if parent:
                    parent['enfants'] = [e for e in parent['enfants'] if e is not noeud]
                racines.append(noeud)
                parcourir(noeud)

        for noeud in noeuds.values():
            noeud.pop('chef_id')
            noeud['nb_membres'] = len(noeud['enfants'])
        return Response(racines)
