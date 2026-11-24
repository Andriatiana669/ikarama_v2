# backend/ikarama/vues.py
"""
Briques communes aux vues de l'API, pour écrire le moins de code possible
dans chaque application.
"""
import io
import json
import re

from django.db import transaction
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

VRAI = ('true', '1', 'oui', 'yes')


class FiltresMixin:
    """
    Filtres simples par paramètre d'URL, déclarés en une ligne :

        filtres = {'pole': 'pole_id', 'type': 'type'}

    -> ?pole=3&type=PROJET  devient  .filter(pole_id=3, type='PROJET')
    Plusieurs valeurs séparées par des virgules : ?type=A,B  -> type__in
    """
    filtres = {}

    def filtrer(self, queryset):
        for parametre, champ in self.filtres.items():
            valeur = self.request.query_params.get(parametre)
            if valeur in (None, ''):
                continue
            if ',' in valeur:
                queryset = queryset.filter(**{f'{champ}__in': [v for v in valeur.split(',') if v]})
            else:
                queryset = queryset.filter(**{champ: valeur})
        return queryset

    def filter_queryset(self, queryset):
        # Étape standard de DRF (liste, export, détail) : les filtres s'appliquent même si la vue
        # redéfinit get_queryset(). Ne pas appeler filtrer() une deuxième fois dans get_queryset().
        return super().filter_queryset(self.filtrer(queryset))


class ActifMixin:
    """
    Pour les modèles avec un champ `actif` :
    - la liste ne montre que les éléments actifs, sauf ?inclure_inactifs=true ;
    - ?archives=1 ne montre que les éléments archivés ;
    - DELETE désactive l'élément au lieu de le supprimer (rien n'est perdu).
    """

    def get_queryset(self):
        queryset = super().get_queryset()
        parametres = self.request.query_params
        if parametres.get('archives', '').lower() in VRAI:       # ?archives=1 : seulement les éléments archivés
            return queryset.filter(actif=False)
        if parametres.get('inclure_inactifs', '').lower() in VRAI:
            return queryset
        if self.action in ('list', 'exporter'):
            return queryset.filter(actif=True)
        return queryset

    def destroy(self, request, *args, **kwargs):
        objet = self.get_object()
        objet.actif = False
        objet.save(update_fields=['actif'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ModeleViewSet(FiltresMixin, viewsets.ModelViewSet):
    """ModelViewSet + filtres déclaratifs."""


class ModeleActifViewSet(ActifMixin, ModeleViewSet):
    """ModelViewSet + filtres + désactivation au lieu de suppression."""


# ------------------------------------------------------------------
# Ordre manuel (poignées ≡ du frontend)
# ------------------------------------------------------------------
class OrdreMixin:
    """
    POST <ressource>/reordonner/   {"ids": [5, 2, 9]}
    Les éléments reçus prennent, dans cet ordre, les valeurs d'« ordre » qu'ils avaient déjà.
    On peut donc réordonner une seule page d'une liste paginée sans toucher aux autres pages.
    Le modèle doit avoir un champ « ordre » (voir ikarama/modeles.py > Ordonnable).
    """

    @action(detail=False, methods=['post'])
    def reordonner(self, request):
        ids = [int(i) for i in request.data.get('ids', []) if str(i).isdigit()]
        objets = {o.pk: o for o in self.get_queryset().filter(pk__in=ids)}
        if len(objets) != len(set(ids)):
            return Response({'detail': 'Liste à réordonner invalide.'}, status=status.HTTP_400_BAD_REQUEST)
        ordres = sorted(o.ordre for o in objets.values())
        with transaction.atomic():
            for ordre, pk in zip(ordres, ids):
                if objets[pk].ordre != ordre:
                    objets[pk].ordre = ordre
                    objets[pk].save(update_fields=['ordre'])
        return Response(status=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------
# Export Excel commun à tous les tableaux
# ------------------------------------------------------------------
def _valeur_cellule(donnees, cle):
    valeur = donnees
    for morceau in cle.split('.'):
        valeur = valeur.get(morceau) if isinstance(valeur, dict) else None
    if isinstance(valeur, list):
        return ', '.join(str(v.get('nom_affiche') or v.get('nom') or v.get('valeur') or '') if isinstance(v, dict)
                         else str(v) for v in valeur)
    if isinstance(valeur, dict):
        if valeur.get('progression'):   # statut en cours : « Terminé 3/5 »
            p = valeur['progression']
            return f"{valeur.get('nom')} {p['au_statut']}/{p['total']}"
        return valeur.get('nom_affiche') or valeur.get('nom') or ''
    if isinstance(valeur, bool):
        return 'Oui' if valeur else 'Non'
    return '' if valeur is None else valeur


def reponse_excel(nom, colonnes, lignes):
    """Fichier Excel (titres marine, largeurs ajustées) : colonnes = [{cle, libelle}], lignes = dictionnaires."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    classeur = Workbook()
    feuille = classeur.active
    nom = re.sub(r'[^\w\- ]', '', nom or 'Export')[:30] or 'Export'
    feuille.title = nom
    feuille.append([c.get('libelle', c.get('cle')) for c in colonnes])
    for cellule in feuille[1]:
        cellule.font = Font(bold=True, color='FFFFFF')
        cellule.fill = PatternFill('solid', fgColor='18355D')
    for ligne in lignes:
        feuille.append([_valeur_cellule(ligne, c.get('cle', '')) for c in colonnes])
    for index, colonne in enumerate(colonnes, start=1):
        largeur = max([len(str(colonne.get('libelle', '')))] +
                      [len(str(feuille.cell(row=r, column=index).value or '')) for r in range(2, min(feuille.max_row, 200) + 1)])
        feuille.column_dimensions[get_column_letter(index)].width = min(max(10, largeur + 2), 60)
    feuille.freeze_panes = 'A2'

    flux = io.BytesIO()
    classeur.save(flux)
    reponse = HttpResponse(flux.getvalue(),
                           content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    reponse['Content-Disposition'] = f'attachment; filename="{nom}.xlsx"'
    return reponse


class ExportExcelMixin:
    """
    GET <ressource>/exporter/?colonnes=[{"cle":"nom","libelle":"Nom"}, ...]&nom=Affaires
    + les mêmes filtres et la même recherche que la liste.
    Les colonnes viennent du frontend : on exporte exactement ce que l'utilisateur voit.
    Les clés pointées (« cree_par_details.nom_affiche ») et les listes de personnes sont gérées.
    Une vue dont les lignes ne viennent pas d'un queryset redéfinit lignes_export().
    """

    def lignes_export(self):
        return self.get_serializer(self.filter_queryset(self.get_queryset()), many=True).data

    @action(detail=False, methods=['get'])
    def exporter(self, request):
        try:
            colonnes = json.loads(request.query_params.get('colonnes', '[]'))
        except ValueError:
            colonnes = []
        if not colonnes:
            return Response({'detail': 'Aucune colonne à exporter.'}, status=status.HTTP_400_BAD_REQUEST)
        return reponse_excel(request.query_params.get('nom', 'Export'), colonnes, self.lignes_export())
