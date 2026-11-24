# backend/gsheets/import_ancien.py
"""
« Import ancienne donnée » d'une feuille : lit les anciens fichiers .xlsx avec LEURS colonnes et crée au passage
les Projets / Communes et Descriptions manquants.

  GET  import-ancien/modele/?feuille=<id>       modèle (colonnes de l'ancien fichier)
  POST import-ancien/importer/?feuille=<id>     aperçu (simulation) puis import

Pour chaque ligne du fichier :
  Affaire      : Num affaire + Nom affaire (doit exister ; on doit en être responsable, ou administrateur)
  Prestation   : par son nom (doit exister) ; cochée pour l'affaire si besoin
  Feuille      : élargie à l'affaire + prestation si elles ne sont dans aucune autre feuille
  Projet       : retrouvé par son nom, sinon créé (Date de livraison du fichier, 1er rendement objectif de la prestation)
  Description  : retrouvée par son nom, sinon créée (Quantité du fichier ; mise à jour si elle existe)
  Ligne        : Employé, Contrôleur (matricule ou identifiant), Statut, Commentaires, Nombre de reprises, Critères ;
                 Temps de prod, Temps de contrôle, Date de début seulement tant que personne n'a pointé sur la ligne
                 (au premier pointage, les temps et la date viennent des pointages).
  Ignorées     : ID (lignes renumérotées), Unité (celle de la prestation), Note de qualité (recalculée).
Une personne ou un statut introuvable laisse la case vide : la ligne est importée avec un avertissement.
"""
from datetime import date as Date
from decimal import Decimal, InvalidOperation

from rest_framework import serializers, viewsets

from autorisations.permissions import est_administrateur
from ikarama.importation import ColonneImport, ImportExcelMixin, lire_date
from marches.models import Affaire, AffairePrestation, Description, Prestation, Projet, RendementObjectif, Statut
from utilisateurs.models import Employe

from .models import LigneFeuille, NoteCritere, PerimetreFeuille
from .services import feuilles_visibles, peut_gerer, synchroniser


def moi(request):
    return getattr(request.user, 'employe', None)


def nombre(valeur, colonne):
    if valeur in (None, ''):
        return None
    try:
        return Decimal(str(valeur).replace(',', '.').replace(' ', '').replace('\u202f', ''))
    except InvalidOperation:
        raise serializers.ValidationError({colonne: f'nombre invalide : « {valeur} »'})


class ImportAncienViewSet(ImportExcelMixin, viewsets.GenericViewSet):
    module = 'gsheets'
    verbes_actions = {'modele': 'voir', 'importer': 'modifier'}
    import_nom = 'Ancienne donnee'
    import_explications = [
        'Colonnes de vos anciens fichiers : gardez les titres (l’ordre n’a pas d’importance).',
        'L’affaire et la prestation doivent déjà exister (Marchés > Ajouter un marché) ; les projets / communes et '
        'descriptions manquants sont créés.',
        'Temps de prod, Temps de contrôle et Date de début sont remplacés par les pointages dès qu’on pointe sur la ligne.',
    ]
    import_alias = {}

    def _feuille(self):
        feuille = feuilles_visibles(self.request.user).filter(pk=self.request.query_params.get('feuille')).first()
        if feuille is None:
            raise serializers.ValidationError({'fichier': 'Feuille introuvable (?feuille=<id>).'})
        # Données de la feuille : règle métier (créateur ou responsable d'une de ses affaires)
        if not peut_gerer(self.request.user, feuille):
            raise serializers.ValidationError({'fichier': 'Seuls le créateur de la feuille et les responsables de ses affaires importent ses données.'})
        return feuille

    def get_import_colonnes(self):
        self._feuille()   # vérifie la feuille et le droit d'importer
        return [
            ColonneImport('id', 'ID', lecture_seule=True, largeur=8, aide='Ignoré : les lignes sont renumérotées.'),
            ColonneImport('employe', 'Employé', largeur=16, exemple='PR00123_Jean', aide='Matricule ou identifiant.'),
            ColonneImport('num_affaire', 'Num affaire', largeur=12, exemple='AF-01'),
            ColonneImport('nom_affaire', 'Nom affaire', requis=True, largeur=26, exemple='Recensement Analamanga',
                          aide='Avec le Num affaire, désigne une affaire existante.'),
            ColonneImport('prestation', 'Prestation', requis=True, largeur=22, exemple='Saisie de fiches', aide='Prestation existante.'),
            ColonneImport('projet', 'Projet/Commune', requis=True, largeur=22, exemple='Commune Ambohidratrimo',
                          autres_libelles=['Projet / Commune', 'Projet', 'Commune'], aide='Créé s’il n’existe pas.'),
            ColonneImport('description', 'Description', requis=True, largeur=22, exemple='Ménages', aide='Créée si elle n’existe pas.'),
            ColonneImport('unite', 'Unité', lecture_seule=True, largeur=10, aide='Ignorée : unité de la prestation.'),
            ColonneImport('quantite', 'Quantité', largeur=10, exemple='1000'),
            ColonneImport('temps_prod', 'Temps de prod', largeur=12, exemple='7.5', aide='En heures.'),
            ColonneImport('date_debut', 'Date de début', largeur=14, exemple='02/11/2026'),
            ColonneImport('statut', 'Statut', largeur=14, exemple='En cours', aide='Nom d’un statut existant.'),
            ColonneImport('commentaires', 'Commentaires', largeur=30),
            ColonneImport('controleur', 'Contrôleur', largeur=16, exemple='PR00124', aide='Matricule ou identifiant.'),
            ColonneImport('temps_controle', 'Temps de contrôle', largeur=12, exemple='1', aide='En heures.'),
            ColonneImport('nb_reprises', 'Nombre de reprises', largeur=12, exemple='0'),
            ColonneImport('date_livraison', 'Date de livraison', largeur=14, exemple='15/12/2026',
                          aide='Obligatoire quand le projet / la commune est créé.'),
            ColonneImport('note_qualite', 'Note de qualité', lecture_seule=True, largeur=12, aide='Ignorée : recalculée.'),
            ColonneImport('criteres', 'Critère', multiple=True, largeur=10, exemple=[4, 5],
                          aide='Notes de 1 à 5 des critères de la feuille, dans l’ordre (Critère 1, Critère 2…).'),
        ]

    # ------------------------------------------------------------------
    def _personne(self, valeur, avertissements, libelle):
        texte = str(valeur or '').strip()
        if not texte:
            return None
        matricule = texte.split('_')[0].upper()
        personne = Employe.objects.filter(code_barre__iexact=matricule).first()
        if personne is None:
            avertissements.append(f'{libelle} : « {texte} » introuvable, case laissée vide.')
        return personne

    def importer_ligne(self, valeurs):
        feuille = self._feuille()
        utilisateur = moi(self.request)
        avertissements = []
        texte = lambda cle: str(valeurs.get(cle) or '').strip()

        # Affaire
        affaires = Affaire.objects.filter(nom__iexact=texte('nom_affaire'))
        if texte('num_affaire'):
            affaires = affaires.filter(num_affaire__iexact=texte('num_affaire'))
        affaires = list(affaires[:2])
        if not affaires:
            raise serializers.ValidationError({'nom_affaire': 'affaire introuvable : créez-la dans Marchés > Ajouter un marché.'})
        if len(affaires) > 1:
            raise serializers.ValidationError({'nom_affaire': 'plusieurs affaires correspondent : précisez le Num affaire.'})
        affaire = affaires[0]
        if not (est_administrateur(self.request.user) or affaire.responsables.filter(pk=getattr(utilisateur, 'pk', None)).exists()):
            raise serializers.ValidationError({'nom_affaire': f'vous n’êtes pas responsable de l’affaire « {affaire.nom} ».'})

        # Prestation (cochée pour l'affaire si besoin)
        prestation = Prestation.objects.filter(nom__iexact=texte('prestation')).first()
        if prestation is None:
            raise serializers.ValidationError({'prestation': 'prestation introuvable : créez-la dans Marchés > Ajouter un marché.'})
        AffairePrestation.objects.get_or_create(affaire=affaire, prestation=prestation)

        # Feuille élargie à l'affaire + prestation
        if not feuille.perimetres.filter(affaire=affaire, prestation=prestation).exists():
            autre = PerimetreFeuille.objects.filter(affaire=affaire, prestation=prestation).exclude(feuille=feuille).select_related('feuille').first()
            if autre:
                raise serializers.ValidationError({'prestation': f'cette prestation de l’affaire est déjà dans la feuille « {autre.feuille.nom} ».'})
            PerimetreFeuille.objects.create(feuille=feuille, affaire=affaire, prestation=prestation)

        # Projet / Commune
        cree = []
        projet = Projet.objects.filter(affaire=affaire, prestation=prestation, nom__iexact=texte('projet')).first()
        livraison = lire_date(valeurs['date_livraison']) if texte('date_livraison') else None
        if projet is None:
            rendement = RendementObjectif.objects.filter(prestation=prestation).order_by('ordre', 'id').first()
            if rendement is None:
                raise serializers.ValidationError({'prestation': 'la prestation n’a aucun rendement objectif.'})
            if livraison is None:
                raise serializers.ValidationError({'date_livraison': 'obligatoire pour créer le projet / la commune.'})
            projet = Projet.objects.create(affaire=affaire, prestation=prestation, nom=texte('projet'), rendement=rendement,
                                           date_livraison=livraison, cree_par=utilisateur)
            cree.append('projet')

        # Description (la ligne de feuille est créée automatiquement)
        quantite = nombre(valeurs.get('quantite'), 'quantite')
        description = Description.objects.filter(projet=projet, nom__iexact=texte('description')).first()
        if description is None:
            description = Description.objects.create(projet=projet, nom=texte('description'), quantite=quantite, cree_par=utilisateur)
            cree.append('description')
        elif quantite is not None and description.quantite != quantite:
            description.quantite = quantite
            description.save()
        synchroniser(feuille)
        ligne = LigneFeuille.objects.filter(feuille=feuille, description=description).first()
        if ligne is None:
            raise serializers.ValidationError({'description': 'la ligne de feuille n’a pas pu être créée.'})

        # Données de la ligne
        champs = []
        from pointages.services import colonnes_verrouillees
        verrouillees = colonnes_verrouillees(ligne)
        for cle, libelle in (('employe', 'Employé'), ('controleur', 'Contrôleur')):
            if cle in valeurs:
                personne = self._personne(valeurs.get(cle), avertissements, libelle)
                if cle in verrouillees and (personne.pk if personne else None) != getattr(ligne, f'{cle}_id'):
                    # Du temps a déjà été pointé : la personne ne peut plus changer (comme dans la feuille)
                    avertissements.append(f'{libelle} verrouillé (temps déjà pointé) : valeur du fichier ignorée.')
                    continue
                setattr(ligne, cle, personne)
                champs.append(cle)
        if texte('statut'):
            statut = Statut.objects.filter(nom__iexact=texte('statut')).first()
            if statut is None:
                avertissements.append(f'Statut « {texte("statut")} » introuvable : statut inchangé.')
            else:
                ligne.statut = statut
                champs.append('statut')
        if 'commentaires' in valeurs:
            ligne.commentaires = texte('commentaires')
            champs.append('commentaires')
        reprises = nombre(valeurs.get('nb_reprises'), 'nb_reprises')
        if reprises is not None:
            ligne.nb_reprises = int(reprises)
            champs.append('nb_reprises')
        # Temps et date de début : seulement tant que personne n'a pointé sur la ligne
        if ligne.parts_pointage.exists():
            if any(texte(c) for c in ('temps_prod', 'temps_controle', 'date_debut')):
                avertissements.append('Des pointages existent : temps et date de début viennent des pointages (valeurs du fichier ignorées).')
        else:
            for cle in ('temps_prod', 'temps_controle'):
                if cle in valeurs:
                    setattr(ligne, cle, nombre(valeurs.get(cle), cle))
                    champs.append(cle)
            if texte('date_debut'):
                ligne.date_debut = lire_date(valeurs['date_debut'])
                champs.append('date_debut')
        if champs:
            ligne.modifie_par = utilisateur
            ligne.save(update_fields=champs + ['modifie_par', 'modifie_le'])

        # Critères
        notes = [n for n in (valeurs.get('criteres') or [])]
        if any(n not in (None, '') for n in notes):
            if not feuille.utiliser_criteres:
                avertissements.append('La feuille n’utilise pas les critères : notes ignorées.')
            else:
                criteres = list(feuille.criteres.order_by('numero'))
                for critere, valeur in zip(criteres, notes):
                    note = nombre(valeur, 'criteres')
                    if note is None:
                        continue
                    if not 1 <= note <= 5:
                        raise serializers.ValidationError({'criteres': f'note de 1 à 5 attendue (Critère {critere.numero}).'})
                    NoteCritere.objects.update_or_create(ligne=ligne, critere=critere, defaults={'note': note})
                if len(notes) > len(criteres) and any(n not in (None, '') for n in notes[len(criteres):]):
                    avertissements.append(f'La feuille n’a que {len(criteres)} critère(s) : notes en trop ignorées.')

        libelle = f"{affaire.nom} › {prestation.nom} › {projet.nom} › {description.nom}"
        if cree:
            libelle += f" ({' et '.join(c + ' créé' + ('e' if c == 'description' else '') for c in cree)})"
        return ('creation' if 'description' in cree else 'modification'), libelle, avertissements
