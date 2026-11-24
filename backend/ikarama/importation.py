# backend/ikarama/importation.py
"""
Import Excel (.xlsx) commun à toute l'application.

Une vue l'ajoute avec ImportExcelMixin et décrit ses colonnes :

    class PrestationViewSet(ImportExcelMixin, ...):
        import_nom = 'Prestations'
        import_colonnes = [
            ColonneImport('nom', 'Nom prestation', requis=True, exemple='Saisie de fiches'),
            ColonneImport('rendements', 'Rendement objectif', multiple=True, exemple=['120', '80']),
        ]
        def importer_ligne(self, valeurs): ...   # crée ou modifie ; lève ValidationError en cas d'erreur

Elle obtient :
    GET  <ressource>/modele/     le fichier modèle (colonnes + onglet « Aide » avec exemples)
    POST <ressource>/importer/   fichier=<.xlsx>, simulation=1 pour l'aperçu (rien n'est enregistré)

Chaque ligne est traitée dans un point de sauvegarde : une ligne en erreur n'empêche pas les autres.
En simulation, tout est fait puis annulé : l'aperçu montre exactement ce que donnera l'import.

Options :
  - get_import_colonnes()      colonnes calculées selon la demande (ex. critères d'une feuille) ;
  - ColonneImport(lecture_seule=True)  colonne d'information du modèle, ignorée à l'import ;
  - import_cle_groupe = 'nom'  les lignes qui ont la même valeur dans cette colonne sont traitées
                               ensemble (importer_ligne reçoit alors une LISTE de lignes) ;
  - import_lignes_modele()     lignes déjà remplies dans le modèle (modifier puis réimporter) ;
  - importer_ligne peut renvoyer ('inchange', libellé) quand rien n'a changé, et un 3e élément :
    une liste d'avertissements (la ligne est importée, l'aperçu les affiche).
"""
from datetime import date, datetime, time
import io
import re
import unicodedata
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

MAX_LIGNES = 2000
MAX_OCTETS = 5 * 1024 * 1024
MARINE = '18355D'


@dataclass
class ColonneImport:
    cle: str
    libelle: str
    requis: bool = False
    aide: str = ''
    exemple: object = ''
    # Colonnes répétées : « Rendement objectif 1 », « Rendement objectif 2 »… -> une liste
    multiple: bool = False
    nb_dans_modele: int = 3
    largeur: int = 22
    autres_libelles: list = field(default_factory=list)
    # Colonne d'information (remplie dans le modèle, ignorée à l'import)
    lecture_seule: bool = False


def normaliser(texte):
    texte = unicodedata.normalize('NFKD', str(texte or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', ' ', texte.lower()).strip()


def lire_date(valeur):
    """Date Excel ou texte « 09/11/2026 » / « 2026-11-09 » -> date."""
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    texte = str(valeur or '').strip()
    for format_ in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y'):
        try:
            return datetime.strptime(texte, format_).date()
        except ValueError:
            pass
    raise ValueError(f"date invalide : « {texte} » (attendu JJ/MM/AAAA)")


def lire_heure(valeur):
    """Heure Excel ou texte « 07:30 » / « 7h30 » -> time."""
    if isinstance(valeur, datetime):
        return valeur.time().replace(second=0, microsecond=0)
    if isinstance(valeur, time):
        return valeur.replace(second=0, microsecond=0)
    if isinstance(valeur, (int, float)) and 0 <= valeur < 1:   # fraction de journée
        minutes = round(valeur * 24 * 60)
        return time(minutes // 60, minutes % 60)
    texte = str(valeur or '').strip().lower().replace('h', ':')
    try:
        heures, _, minutes = texte.partition(':')
        return time(int(heures), int(minutes or 0))
    except ValueError:
        raise ValueError(f"heure invalide : « {valeur} » (attendu HH:MM)")


def separer(valeur):
    """« PR001; PR002 , PR003 » -> ['PR001', 'PR002', 'PR003']"""
    return [v.strip() for v in re.split(r'[;,\n]+', str(valeur or '')) if v.strip()]


def messages_erreur(exc, colonnes, alias=None):
    """ValidationError DRF / Django -> liste de messages lisibles « Colonne : message »."""
    libelles = {c.cle: c.libelle for c in colonnes}
    for champ, cle in (alias or {}).items():   # champ du serializer -> colonne du fichier
        libelles[champ] = libelles.get(cle, cle)
    detail = getattr(exc, 'detail', None) or getattr(exc, 'message_dict', None) or getattr(exc, 'messages', None) or str(exc)
    messages = []

    def parcourir(valeur, champ=None):
        if isinstance(valeur, dict):
            for cle, v in valeur.items():
                parcourir(v, None if cle in ('non_field_errors', '__all__', 'detail') else cle)
        elif isinstance(valeur, (list, tuple)):
            for v in valeur:
                parcourir(v, champ)
        else:
            texte = str(valeur)
            messages.append(f"{libelles.get(champ, champ)} : {texte}" if champ else texte)

    parcourir(detail)
    return messages or ['Ligne invalide.']


class ImportExcelMixin:
    import_nom = 'Import'
    import_colonnes: list = []
    import_explications: list = []   # phrases ajoutées en tête de l'onglet « Aide »
    import_alias: dict = {}          # nom d'un champ du serializer -> clé de colonne (pour les messages)
    import_cle_groupe: str = ''      # lignes regroupées par la valeur de cette colonne

    def get_import_colonnes(self):
        return self.import_colonnes

    def import_lignes_modele(self):
        """Lignes déjà remplies dans le modèle : une liste de dict {cle: valeur} (vide par défaut)."""
        return []

    # --- À fournir par la vue ------------------------------------------
    def importer_ligne(self, valeurs):
        """Crée ou modifie un élément. Renvoie ('creation' | 'modification', libellé). Lève ValidationError."""
        raise NotImplementedError

    def import_onglets_reference(self):
        """Onglets en plus dans le modèle : [(titre, [entêtes], [lignes])] (ex. liste des matricules)."""
        return []

    # --- Modèle ----------------------------------------------------------
    def _entetes(self):
        entetes = []
        for c in self.get_import_colonnes():
            titre = c.libelle + (' *' if c.requis else '')
            if c.multiple:
                entetes += [(c, f'{c.libelle} {i}' + (' *' if c.requis and i == 1 else '')) for i in range(1, c.nb_dans_modele + 1)]
            else:
                entetes.append((c, titre))
        return entetes

    @action(detail=False, methods=['get'])
    def modele(self, request):
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter

        classeur = Workbook()
        feuille = classeur.active
        feuille.title = self.import_nom[:30]
        entete_style = (Font(bold=True, color='FFFFFF'), PatternFill('solid', fgColor=MARINE))
        entete_info = (Font(bold=True, color='FFFFFF'), PatternFill('solid', fgColor='8A94A6'))
        entetes = self._entetes()
        for i, (colonne, titre) in enumerate(entetes, start=1):
            cellule = feuille.cell(row=1, column=i, value=titre + (' (info)' if colonne.lecture_seule else ''))
            cellule.font, cellule.fill = entete_info if colonne.lecture_seule else entete_style
            feuille.column_dimensions[get_column_letter(i)].width = colonne.largeur
        feuille.freeze_panes = 'A2'
        # Modèle prérempli (ex. lignes actuelles d'une feuille)
        gris = PatternFill('solid', fgColor='EEF1F5')
        for ligne in self.import_lignes_modele():
            valeurs = []
            for colonne, _ in entetes:
                valeur = ligne.get(colonne.cle)
                if colonne.multiple:
                    rang = sum(1 for c, _ in entetes[:len(valeurs)] if c is colonne)
                    valeur = (valeur or [])[rang] if rang < len(valeur or []) else None
                valeurs.append(valeur)
            feuille.append(valeurs)
            for i, (colonne, _) in enumerate(entetes, start=1):
                if colonne.lecture_seule:
                    feuille.cell(row=feuille.max_row, column=i).fill = gris

        # Onglet « Aide » : explications, colonnes et exemples (jamais importé)
        aide = classeur.create_sheet('Aide')
        aide.column_dimensions['A'].width = 30
        aide.column_dimensions['B'].width = 14
        aide.column_dimensions['C'].width = 70
        aide.column_dimensions['D'].width = 36
        aide.append([f'Import : {self.import_nom}'])
        aide['A1'].font = Font(bold=True, size=14, color=MARINE)
        for phrase in [
            f'Remplissez l’onglet « {feuille.title} » à partir de la ligne 2 (la ligne 1 contient les titres).',
            'Les colonnes marquées * sont obligatoires. Ne renommez pas les titres.',
            *self.import_explications,
            f'{MAX_LIGNES} lignes au maximum par fichier.',
        ]:
            aide.append([phrase])
        aide.append([])
        aide.append(['Colonne', 'Obligatoire', 'Contenu attendu', 'Exemple'])
        for cellule in aide[aide.max_row]:
            cellule.font, cellule.fill = entete_style
        for c in self.get_import_colonnes():
            exemple = ' | '.join(map(str, c.exemple)) if isinstance(c.exemple, (list, tuple)) else c.exemple
            titre = f'{c.libelle} 1, 2, 3…' if c.multiple else c.libelle
            obligatoire = 'Information (ignorée à l’import)' if c.lecture_seule else ('Oui' if c.requis else 'Non')
            aide.append([titre, obligatoire, c.aide, exemple])
            aide.cell(row=aide.max_row, column=3).alignment = Alignment(wrap_text=True, vertical='top')

        for titre, entetes, lignes in self.import_onglets_reference():
            onglet = classeur.create_sheet(titre[:30])
            onglet.append(entetes)
            for cellule in onglet[1]:
                cellule.font, cellule.fill = entete_style
            for ligne in lignes:
                onglet.append(list(ligne))
            for i in range(1, len(entetes) + 1):
                onglet.column_dimensions[get_column_letter(i)].width = 28

        flux = io.BytesIO()
        classeur.save(flux)
        reponse = HttpResponse(flux.getvalue(),
                               content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        reponse['Content-Disposition'] = f'attachment; filename="Modele_import_{normaliser(self.import_nom).replace(" ", "_")}.xlsx"'
        return reponse

    # --- Lecture ---------------------------------------------------------
    def _lire(self, fichier):
        from openpyxl import load_workbook

        if not fichier:
            raise serializers.ValidationError({'fichier': 'Choisissez un fichier Excel (.xlsx).'})
        if not fichier.name.lower().endswith('.xlsx'):
            raise serializers.ValidationError({'fichier': 'Seuls les fichiers Excel .xlsx sont acceptés.'})
        if fichier.size > MAX_OCTETS:
            raise serializers.ValidationError({'fichier': 'Fichier trop volumineux (5 Mo au maximum).'})
        try:
            classeur = load_workbook(fichier, read_only=True, data_only=True)
        except Exception:
            raise serializers.ValidationError({'fichier': 'Ce fichier ne peut pas être lu comme un classeur Excel.'})
        feuille = classeur.worksheets[0]   # le premier onglet (l'onglet « Aide » est ignoré)
        lignes = feuille.iter_rows(values_only=True)
        titres = [re.sub(r' info$', '', normaliser(t)).strip() for t in (next(lignes, None) or [])]
        colonnes = [c for c in self.get_import_colonnes() if not c.lecture_seule]

        # Correspondance titre -> colonne
        positions = {}
        for c in colonnes:
            noms = [normaliser(n) for n in [c.libelle, *c.autres_libelles]]
            if c.multiple:
                positions[c.cle] = [i for i, t in enumerate(titres) if any(t == n or re.fullmatch(rf'{re.escape(n)} \d+', t) for n in noms)]
            else:
                trouve = next((i for i, t in enumerate(titres) if t in noms), None)
                if trouve is not None:
                    positions[c.cle] = trouve
        manquantes = [c.libelle for c in colonnes if c.requis and positions.get(c.cle) in (None, [])]
        if manquantes:
            raise serializers.ValidationError({'fichier': f"Colonne(s) introuvable(s) : {', '.join(manquantes)}. "
                                                          "Utilisez le modèle téléchargeable."})
        resultat = []
        for numero, ligne in enumerate(lignes, start=2):
            if not ligne or all(v in (None, '') for v in ligne):
                continue
            # Excel renvoie 1234.0 pour un nombre entier : on le remet en 1234
            ligne = [int(v) if isinstance(v, float) and v.is_integer() else v for v in ligne]
            valeurs = {}
            for c in colonnes:
                pos = positions.get(c.cle)
                if c.multiple:
                    valeurs[c.cle] = [ligne[i] for i in (pos or []) if i < len(ligne) and ligne[i] not in (None, '')]
                else:
                    v = ligne[pos] if pos is not None and pos < len(ligne) else None
                    valeurs[c.cle] = v.strip() if isinstance(v, str) else v
            resultat.append((numero, valeurs))
            if len(resultat) > MAX_LIGNES:
                raise serializers.ValidationError({'fichier': f'{MAX_LIGNES} lignes au maximum par fichier.'})
        if not resultat:
            raise serializers.ValidationError({'fichier': 'Le fichier ne contient aucune ligne à importer.'})
        return resultat

    # --- Import ------------------------------------------------------------
    @action(detail=False, methods=['post'])
    def importer(self, request):
        simulation = str(request.data.get('simulation', '')).lower() in ('1', 'true', 'oui')
        lignes = self._lire(request.FILES.get('fichier'))
        rapport = {'simulation': simulation, 'total': len(lignes), 'crees': 0, 'modifies': 0, 'inchanges': 0,
                   'erreurs': 0, 'lignes': []}
        colonnes = self.get_import_colonnes()

        # Lignes regroupées (ex. une feuille sur plusieurs lignes) ou traitées une à une
        if self.import_cle_groupe:
            groupes = {}
            for numero, valeurs in lignes:
                cle = normaliser(valeurs.get(self.import_cle_groupe)) or f'__ligne_{numero}'
                groupes.setdefault(cle, []).append((numero, valeurs))
            unites = [([n for n, _ in g], [v for _, v in g]) for g in groupes.values()]
        else:
            unites = [([numero], valeurs) for numero, valeurs in lignes]

        compteurs = {'creation': 'crees', 'modification': 'modifies', 'inchange': 'inchanges'}
        with transaction.atomic():
            for numeros, valeurs in unites:
                premiere = valeurs[0] if isinstance(valeurs, list) else valeurs
                try:
                    with transaction.atomic():   # une ligne en erreur est annulée seule
                        retour = self.importer_ligne(valeurs)
                    # (action, libellé) ou (action, libellé, avertissements) : la ligne est importée malgré eux
                    type_action, libelle = retour[0], retour[1]
                    messages = list(retour[2]) if len(retour) > 2 else []
                    rapport[compteurs[type_action]] += 1
                except (serializers.ValidationError, DjangoValidationError, IntegrityError, ValueError) as exc:
                    type_action, libelle = 'erreur', self._libelle_brut(premiere)
                    rapport['erreurs'] += 1
                    messages = messages_erreur(exc, colonnes, self.import_alias)
                if len(numeros) > 1:
                    messages = [f"Lignes {', '.join(map(str, numeros))} regroupées."] + messages
                rapport['lignes'].append({'numero': numeros[0], 'action': type_action, 'libelle': libelle,
                                          'messages': messages})
            if simulation:
                transaction.set_rollback(True)   # aperçu : rien n'est enregistré
        if not simulation and rapport['erreurs']:
            self._notifier_import(rapport)
        return Response(rapport, status=status.HTTP_200_OK)

    def _notifier_import(self, rapport):
        """Garde une trace de l'import terminé avec des lignes ignorées (cloche de l'auteur)."""
        employe = getattr(self.request.user, 'employe', None)
        if employe is None:
            return
        from notifications.services import notifier
        notifier([employe], 'import', f"Import « {self.import_nom} » : {rapport['erreurs']} ligne(s) ignorée(s)",
                 message=f"{rapport['crees']} création(s), {rapport['modifies']} mise(s) à jour, {rapport['erreurs']} erreur(s).")

    def _libelle_brut(self, valeurs):
        premier = next((c.cle for c in self.get_import_colonnes() if c.requis and not c.multiple and not c.lecture_seule), None)
        return str(valeurs.get(premier) or '—')
