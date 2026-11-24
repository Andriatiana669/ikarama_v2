# backend/ikarama/pagination.py
from rest_framework.pagination import PageNumberPagination


class PaginationStandard(PageNumberPagination):
    """
    Pagination commune à toute l'API.
    - ?page=2            : numéro de page
    - ?page_size=50      : taille de page (max 500)
    - ?page_size=0       : pas de pagination (listes pour les menus déroulants)
    """
    page_size_query_param = 'page_size'
    max_page_size = 500

    def paginate_queryset(self, queryset, request, view=None):
        if request.query_params.get(self.page_size_query_param) == '0':
            return None
        return super().paginate_queryset(queryset, request, view)
