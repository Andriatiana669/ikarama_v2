# backend/gsheets/serializers.py
from decimal import Decimal, InvalidOperation

from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import APIException

from marches.models import AffairePrestation, Statut
from utilisateurs.models import Employe
from utilisateurs.serializers import EmployeResumeSerializer

from .models import CritereControle, Feuille, HistoriqueLigne, LigneFeuille, NoteCritere, PerimetreFeuille
from rendements import calculs
from rendements.models import ParametresRendement

from .services import est_concerne, peut_gerer, personnes_de_l_affaire, synchroniser

MAX_CRITERES = 30


def texte(nombre):
    return None if nombre is None else str(nombre)


def employe_connecte(serializer):
    request = serializer.context.get('request')
    return getattr(getattr(request, 'user', None), 'employe', None)


class CritereSerializer(serializers.ModelSerializer):
    class Meta:
        model = CritereControle
        fields = ['id', 'numero', 'commentaire']


class PerimetreSerializer(serializers.ModelSerializer):
    num_affaire = serializers.CharField(source='affaire.num_affaire', read_only=True)
    nom_affaire = serializers.CharField(source='affaire.nom', read_only=True)
    nom_prestation = serializers.CharField(source='prestation.nom', read_only=True)

    class Meta:
        model = PerimetreFeuille
        fields = ['affaire', 'num_affaire', 'nom_affaire', 'prestation', 'nom_prestation']


class FeuilleSerializer(serializers.ModelSerializer):
    """
    Écriture :
        {"nom": "...", "perimetres": [{"affaire": 1, "prestation": 2}, ...],
         "criteres": ["Orthographe", "Exhaustivité", ...]}      # un commentaire par critère
    """
    perimetres = PerimetreSerializer(many=True, read_only=True)
    criteres = CritereSerializer(many=True, read_only=True)
    perimetres_saisis = serializers.ListField(child=serializers.DictField(), write_only=True, source='perimetres_entree')
    criteres_saisis = serializers.ListField(child=serializers.CharField(allow_blank=True), write_only=True,
                                            source='criteres_entree', required=False)
    cree_par_details = EmployeResumeSerializer(source='cree_par', read_only=True)
    nb_lignes = serializers.IntegerField(read_only=True, required=False)
    avancement_moyen = serializers.FloatField(read_only=True, required=False)
    peut_gerer = serializers.SerializerMethodField()
    droits = serializers.SerializerMethodField()
    mon_role = serializers.SerializerMethodField()

    # Statuts de ses lignes avec leur nombre (« Livré 10, En cours 5 »)
    statuts = serializers.SerializerMethodField()

    def get_statuts(self, obj):
        """Calculé une seule fois pour toute la page de feuilles."""
        cache = self.context.setdefault('_statuts_feuilles', {})
        if obj.pk not in cache:
            from django.db.models import Count
            parent = getattr(self, 'parent', None)
            feuilles = [f.pk for f in parent.instance] if parent is not None and parent.instance is not None else [obj.pk]
            for feuille_id in feuilles:
                cache.setdefault(feuille_id, [])
            comptes = (LigneFeuille.objects.filter(feuille_id__in=feuilles, description__isnull=False)
                       .values('feuille_id', 'statut_id', 'statut__nom', 'statut__couleur', 'statut__ordre')
                       .annotate(nombre=Count('id')).order_by('statut__ordre', 'statut__nom'))
            for c in comptes:
                cache.setdefault(c['feuille_id'], []).append({
                    'id': c['statut_id'], 'nom': c['statut__nom'] or 'Sans statut', 'couleur': c['statut__couleur'] or '#E5E7EB',
                    'nombre': c['nombre'],
                })
        return cache.get(obj.pk, [])

    class Meta:
        model = Feuille
        fields = ['id', 'nom', 'utiliser_criteres', 'perimetres', 'criteres', 'perimetres_saisis', 'criteres_saisis', 'nb_lignes',
                  'statuts',
                  'avancement_moyen', 'peut_gerer', 'droits', 'mon_role', 'cree_par_details', 'cree_le', 'modifie_le']

    def get_peut_gerer(self, obj):
        return peut_gerer(self.context['request'].user, obj)

    def get_droits(self, obj):
        """
        Ce que l'écran peut proposer : la FEUILLE (modifier, supprimer : Paramètres > Autorisation)
        et ses DONNÉES (importer : règle métier, créateur ou responsable d'une de ses affaires).
        """
        from .services import droit_feuille
        user = self.context['request'].user
        return {'modifier': droit_feuille(user, obj, 'modifier'), 'supprimer': droit_feuille(user, obj, 'supprimer'),
                'importer_donnees': peut_gerer(user, obj)}

    def get_mon_role(self, obj):
        moi = employe_connecte(self)
        if moi is None:
            return None
        affaires = [p.affaire for p in obj.perimetres.all()]
        if obj.cree_par_id == moi.pk or any(moi in a.responsables.all() for a in affaires):
            return 'RESPONSABLE'
        return 'MEMBRE'

    # --- Validation -----------------------------------------------------
    def validate_perimetres_saisis(self, valeurs):
        moi = employe_connecte(self)
        paires = []
        for v in valeurs:
            try:
                paire = (int(v.get('affaire')), int(v.get('prestation')))
            except (TypeError, ValueError):
                raise serializers.ValidationError('Périmètre invalide.')
            if paire not in paires:
                paires.append(paire)
        if not paires:
            raise serializers.ValidationError('Choisissez au moins une affaire et une de ses prestations.')
        # Affaires où l'on peut créer une feuille (Paramètres > Autorisation : Mes feuilles > Créer)
        from .services import affaires_creables
        utilisateur = self.context['request'].user
        liens = AffairePrestation.objects.filter(
            affaire__in=affaires_creables(moi, utilisateur), affaire_id__in=[a for a, _ in paires],
        ).values_list('affaire_id', 'prestation_id')
        autorisees = set(liens)
        refusees = [p for p in paires if p not in autorisees]
        # Une même Affaire + Prestation ne peut être que dans une seule feuille
        # (le pointage retrouve ainsi toujours une seule ligne pour une description)
        deja = (PerimetreFeuille.objects.filter(affaire_id__in=[a for a, _ in paires])
                .exclude(feuille=self.instance).select_related('affaire', 'prestation', 'feuille'))
        for perimetre in deja:
            if (perimetre.affaire_id, perimetre.prestation_id) in paires:
                raise serializers.ValidationError(
                    f"La prestation « {perimetre.prestation.nom} » de l'affaire « {perimetre.affaire.nom} » "
                    f"est déjà dans la feuille « {perimetre.feuille.nom} ».")
        if refusees:
            raise serializers.ValidationError(
                "Une des affaires choisies n'est pas une de vos affaires (responsable), "
                "ou la prestation n'y est pas cochée.")
        return paires

    def validate(self, donnees):
        # Sans critères : la liste de critères n'est pas obligatoire (les critères existants sont gardés, masqués)
        if donnees.get('utiliser_criteres') is False:
            donnees.pop('criteres_entree', None)
        return donnees

    def validate_criteres_saisis(self, commentaires):
        commentaires = [c.strip() for c in commentaires]
        if len(commentaires) > MAX_CRITERES:
            raise serializers.ValidationError(f'{MAX_CRITERES} critères au maximum.')
        if any(not c for c in commentaires):
            raise serializers.ValidationError('Chaque critère de CTRL doit avoir un commentaire.')
        return commentaires

    # --- Enregistrement -------------------------------------------------
    def _enregistrer(self, feuille, paires, commentaires):
        if paires is not None:
            actuelles = set(feuille.perimetres.values_list('affaire_id', 'prestation_id'))
            for a, p in actuelles - set(paires):
                feuille.perimetres.filter(affaire_id=a, prestation_id=p).delete()
            for a, p in set(paires) - actuelles:
                PerimetreFeuille.objects.create(feuille=feuille, affaire_id=a, prestation_id=p)
        if commentaires is not None:
            # Les critères sont repris dans l'ordre : on garde ceux qui existent (et leurs notes)
            existants = {c.numero: c for c in feuille.criteres.all()}
            for numero, commentaire in enumerate(commentaires, start=1):
                critere = existants.pop(numero, None)
                if critere:
                    if critere.commentaire != commentaire:
                        critere.commentaire = commentaire
                        critere.save(update_fields=['commentaire'])
                else:
                    CritereControle.objects.create(feuille=feuille, numero=numero, commentaire=commentaire)
            for critere in existants.values():   # critères en trop : supprimés avec leurs notes
                critere.delete()
        synchroniser(feuille)

    @transaction.atomic
    def create(self, donnees):
        paires = donnees.pop('perimetres_entree')
        commentaires = donnees.pop('criteres_entree', [])
        feuille = Feuille.objects.create(**donnees)
        self._enregistrer(feuille, paires, commentaires)
        return feuille

    @transaction.atomic
    def update(self, feuille, donnees):
        paires = donnees.pop('perimetres_entree', None)
        commentaires = donnees.pop('criteres_entree', None)
        feuille = super().update(feuille, donnees)
        self._enregistrer(feuille, paires, commentaires)
        return feuille


class StatutResumeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Statut
        fields = ['id', 'nom', 'couleur']


class LigneSerializer(serializers.ModelSerializer):
    """Une ligne : informations du Marché (lecture seule) + saisie."""
    # N'importe quel employé à la lecture ; la règle (responsable ou membre de l'affaire) est dans validate()
    employe = serializers.PrimaryKeyRelatedField(queryset=Employe.objects.all(), allow_null=True, required=False)
    controleur = serializers.PrimaryKeyRelatedField(queryset=Employe.objects.all(), allow_null=True, required=False)
    employe_reprise = serializers.PrimaryKeyRelatedField(queryset=Employe.objects.all(), allow_null=True, required=False)
    statut = serializers.PrimaryKeyRelatedField(queryset=Statut.objects.all(), allow_null=True, required=False)
    statut_controle = serializers.PrimaryKeyRelatedField(queryset=Statut.objects.all(), allow_null=True, required=False)
    marche = serializers.SerializerMethodField()
    employe_details = EmployeResumeSerializer(source='employe', read_only=True)
    controleur_details = EmployeResumeSerializer(source='controleur', read_only=True)
    employe_reprise_details = EmployeResumeSerializer(source='employe_reprise', read_only=True)
    statut_details = StatutResumeSerializer(source='statut', read_only=True)
    statut_controle_details = StatutResumeSerializer(source='statut_controle', read_only=True)
    notes = serializers.SerializerMethodField()
    # Valeurs que la personne voyait avant de modifier : {"avancement": 40, "note_12": "3.50"}.
    # Si quelqu'un d'autre les a changées entre-temps, l'enregistrement est refusé (conflit).
    attendu = serializers.DictField(write_only=True, required=False)
    modifie_par_details = EmployeResumeSerializer(source='modifie_par', read_only=True)
    notes_saisies = serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True),
                                          write_only=True, required=False)
    retiree = serializers.BooleanField(read_only=True)
    peut_modifier = serializers.SerializerMethodField()
    peut_saisir_controle = serializers.SerializerMethodField()
    colonnes_verrouillees = serializers.SerializerMethodField()
    temps_estimatif = serializers.SerializerMethodField()
    alerte_temps = serializers.SerializerMethodField()
    # Colonnes calculées (Paramètres > Rendement & Note)
    rendement_prod = serializers.SerializerMethodField()
    rendement_total = serializers.SerializerMethodField()
    note_rendement = serializers.SerializerMethodField()
    note_qualite = serializers.SerializerMethodField()

    PERSONNES = ('employe', 'controleur', 'employe_reprise')
    # Réservé aux responsables : nombre de reprises et notes des critères
    CHAMPS_CONTROLE = ('nb_reprises', 'notes_saisies')

    class Meta:
        model = LigneFeuille
        fields = ['id', 'numero', 'feuille', 'marche', 'retiree',
                  'employe', 'employe_details', 'controleur', 'controleur_details',
                  'employe_reprise', 'employe_reprise_details', 'statut', 'statut_details',
                  'statut_controle', 'statut_controle_details',
                  'avancement', 'commentaires', 'commentaires_controle', 'commentaires_reprise', 'nb_reprises',
                  'notes', 'notes_saisies',
                  'peut_modifier', 'peut_saisir_controle', 'colonnes_verrouillees',
                  'temps_estimatif', 'alerte_temps', 'temps_prod', 'date_debut', 'rendement_prod', 'temps_controle', 'temps_reprise',
                  'rendement_total', 'note_rendement', 'note_qualite', 'attendu', 'modifie_par_details', 'modifie_le']
        # Les temps et la date de début viendront du Pointage
        read_only_fields = ['numero', 'feuille', 'temps_prod', 'date_debut', 'temps_controle', 'temps_reprise']

    # --- Calculs ------------------------------------------------------
    def _parametres(self):
        if '_parametres' not in self.context:
            self.context['_parametres'] = ParametresRendement.actuels()
        return self.context['_parametres']

    def _quantite(self, obj):
        return obj.description.quantite if obj.description else obj.instantane.get('quantite')

    def _objectif(self, obj):
        return obj.description.projet.rendement.valeur if obj.description else obj.instantane.get('rendement_objectif')

    def _rendement_total(self, obj):
        return calculs.rendement_total(self._quantite(obj), obj.temps_prod, obj.temps_controle, obj.temps_reprise,
                                       self._parametres())

    # --- Temps Estimatif (Paramètres > Temps Estimatif) -------------------
    def _temps_estimatif_heures(self, obj):
        """Quantité ÷ Rendement objectif par jour × heures par jour (None si une donnée manque)."""
        quantite, objectif = self._quantite(obj), self._objectif(obj)
        try:
            quantite, objectif = Decimal(str(quantite)), Decimal(str(objectif))
        except (InvalidOperation, TypeError, ValueError):
            return None
        if not quantite or not objectif:
            return None
        return quantite / objectif * self._parametres().heures_par_jour

    def get_temps_estimatif(self, obj):
        """En heures (texte) ; l'écran l'affiche en heures ou en jours."""
        heures = self._temps_estimatif_heures(obj)
        return None if heures is None else str(heures.quantize(Decimal('0.01')))

    def get_alerte_temps(self, obj):
        """'rouge' (dépassé), 'orange' (proche, selon la marge) ou None ; rien au statut qui active la note."""
        from .models import ParametresTempsEstimatif
        if '_temps_estimatif' not in self.context:
            self.context['_temps_estimatif'] = (ParametresTempsEstimatif.actuels(), Statut.pour_note_rendement())
        reglages, statut_final = self.context['_temps_estimatif']
        from .services import niveau_alerte
        return niveau_alerte(self._temps_estimatif_heures(obj), obj.temps_prod, obj.statut_id, reglages, statut_final)

    # Les nombres sont renvoyés en texte (« 133.33 »), comme les autres décimaux de l'API
    def get_rendement_prod(self, obj):
        return texte(calculs.rendement_prod(self._quantite(obj), obj.temps_prod, self._parametres()))

    def get_rendement_total(self, obj):
        return texte(self._rendement_total(obj))

    def _projets_notables(self, feuille_id):
        """
        Projets de la feuille dont TOUTES les descriptions ont le statut « Active la note de rendement ».
        None si aucun statut n'a ce rôle (la note s'affiche alors toujours).
        """
        cache = self.context.setdefault('_projets_notables', {})
        if feuille_id not in cache:
            statut = Statut.pour_note_rendement()
            if statut is None:
                cache[feuille_id] = None
            else:
                from django.db.models import Count, Q
                comptes = (LigneFeuille.objects.filter(feuille_id=feuille_id, description__isnull=False)
                           .values('description__projet_id')
                           .annotate(total=Count('id'), ok=Count('id', filter=Q(statut=statut))))
                cache[feuille_id] = {c['description__projet_id'] for c in comptes if c['total'] == c['ok']}
        return cache[feuille_id]

    def get_note_rendement(self, obj):
        notables = self._projets_notables(obj.feuille_id)
        if notables is not None and (obj.description is None or obj.description.projet_id not in notables):
            return None   # tout le projet n'a pas encore le statut qui active la note
        return texte(calculs.note_rendement(self._rendement_total(obj), self._objectif(obj), self._parametres()))

    def get_note_qualite(self, obj):
        if obj.feuille.utiliser_criteres:
            return texte(calculs.note_qualite_criteres([n.note for n in obj.notes.all()]))
        return texte(calculs.note_qualite_reprise(obj.temps_prod, obj.temps_reprise, self._parametres()))

    def get_marche(self, obj):
        """Informations du Marché : en direct, ou la copie si la description a été supprimée."""
        d = obj.description
        if d is None:
            return obj.instantane
        projet = d.projet
        return {
            'affaire_id': projet.affaire_id,
            'num_affaire': projet.affaire.num_affaire,
            'nom_affaire': projet.affaire.nom,
            'prestation': projet.prestation.nom,
            'unite': projet.prestation.unite,
            'projet': projet.nom,
            'description': d.nom,
            'quantite': str(d.quantite) if d.quantite is not None else None,
            'rendement_objectif': str(projet.rendement.valeur),
            'date_livraison': projet.date_livraison.isoformat(),
        }

    def get_notes(self, obj):
        return {str(n.critere_id): (str(n.note) if n.note is not None else None) for n in obj.notes.all()}

    def _gestionnaire(self, obj):
        cache = self.context.setdefault('_gestion', {})
        if obj.feuille_id not in cache:
            cache[obj.feuille_id] = peut_gerer(self.context['request'].user, obj.feuille)
        return cache[obj.feuille_id]

    def _verrouillees(self, obj):
        """Colonnes Employé / Contrôleur / Employé reprise déjà pointées (voir pointages/services.py)."""
        from pointages.services import colonnes_verrouillees
        return colonnes_verrouillees(obj)

    def get_colonnes_verrouillees(self, obj):
        return self._verrouillees(obj)

    def get_peut_saisir_controle(self, obj):
        """Nombre de reprises et notes des critères : responsables seulement."""
        return self._gestionnaire(obj)

    def get_peut_modifier(self, obj):
        """Employé, Statut, Avancement, Commentaires, Contrôleur, Employé reprise : responsables et membres."""
        cache = self.context.setdefault('_concerne', {})
        if obj.feuille_id not in cache:
            cache[obj.feuille_id] = est_concerne(self.context['request'].user, obj.feuille)
        return cache[obj.feuille_id]

    # --- Validation -----------------------------------------------------
    def validate(self, donnees):
        ligne = self.instance
        if not self.get_peut_modifier(ligne):
            raise serializers.ValidationError("Vous ne pouvez pas modifier cette ligne.")
        controle = [c for c in self.CHAMPS_CONTROLE if c in donnees]
        if controle and not self.get_peut_saisir_controle(ligne):
            raise serializers.ValidationError("Seuls les responsables peuvent saisir le nombre de reprises et les critères.")
        personnes = [c for c in self.PERSONNES if c in donnees]
        verrouillees = self._verrouillees(ligne)
        for champ in personnes:
            if champ in verrouillees and donnees[champ] != getattr(ligne, champ):
                raise serializers.ValidationError({champ: "Cette colonne est verrouillée : du temps y a déjà été pointé."})
        affaire_id = (ligne.description.projet.affaire_id if ligne.description else ligne.instantane.get('affaire_id'))
        autorisees = None
        for champ in personnes:
            personne = donnees[champ]
            if personne is None:
                continue
            if autorisees is None:
                from marches.models import Affaire
                affaire = Affaire.objects.filter(pk=affaire_id).first()
                autorisees = set(personnes_de_l_affaire(affaire).values_list('pk', flat=True)) if affaire else set()
            if personne.pk not in autorisees:
                raise serializers.ValidationError({champ: "Cette personne n'est ni responsable ni membre de l'affaire."})
        if 'notes_saisies' in donnees:
            criteres = set(ligne.feuille.criteres.values_list('pk', flat=True))
            notes = {}
            for cle, valeur in donnees['notes_saisies'].items():
                if not str(cle).isdigit() or int(cle) not in criteres:
                    raise serializers.ValidationError({'notes_saisies': 'Critère inconnu.'})
                texte = (valeur or '').strip().replace(',', '.')
                try:
                    note = float(texte) if texte else None
                except ValueError:
                    raise serializers.ValidationError({'notes_saisies': f'« {valeur} » n’est pas un nombre.'})
                p = self._parametres()
                if note is not None and not (float(p.note_critere_min) <= note <= float(p.note_critere_max)):
                    raise serializers.ValidationError({'notes_saisies': [
                        f'La note doit être comprise entre {p.note_critere_min.normalize():f} et {p.note_critere_max.normalize():f}.']})
                notes[int(cle)] = note
            donnees['notes_saisies'] = notes
        return donnees

    # --- Valeurs comparables (conflits et historique) ---------------
    LIBELLES = {
        'employe': 'Employé', 'controleur': 'Contrôleur', 'employe_reprise': 'Employé reprise',
        'statut': 'Statut', 'statut_controle': 'Statut de contrôle', 'avancement': 'Avancement', 'commentaires': 'Commentaires',
        'commentaires_controle': 'Commentaires contrôle', 'commentaires_reprise': 'Commentaires reprise',
        'nb_reprises': 'Nombre de reprises',
    }

    @staticmethod
    def _brut(valeur):
        # Forme comparable : identifiant pour une personne ou un statut, nombre ou texte sinon
        if valeur is None or valeur == '':
            return None
        if hasattr(valeur, 'pk'):        # personne ou statut : on compare son numéro
            valeur = valeur.pk          # (puis même format que le numéro envoyé par la page)
        try:
            return str(float(str(valeur).replace(',', '.')))
        except ValueError:
            return str(valeur).strip()

    @staticmethod
    def _lisible(valeur):
        # Texte affiché dans l'historique : « PR00123_Jean », « En cours », « 3,5 »
        if valeur is None or valeur == '':
            return ''
        if hasattr(valeur, 'identifiant'):
            return valeur.identifiant
        if hasattr(valeur, 'nom'):
            return valeur.nom
        if isinstance(valeur, (int, float, Decimal)) and not isinstance(valeur, bool):
            return f'{float(valeur):.2f}'.rstrip('0').rstrip('.').replace('.', ',')
        return str(valeur)

    def _valeurs_actuelles(self, ligne):
        valeurs = {champ: getattr(ligne, champ) for champ in self.LIBELLES}
        for note in ligne.notes.all():
            valeurs[f'note_{note.critere_id}'] = note.note
        return valeurs

    def _verifier_conflit(self, ligne, attendu):
        actuelles = self._valeurs_actuelles(ligne)
        for champ, valeur_vue in (attendu or {}).items():
            if champ in actuelles or champ.startswith('note_'):
                if self._brut(actuelles.get(champ)) != self._brut(valeur_vue):
                    moi = employe_connecte(self)
                    if ligne.modifie_par_id and moi and ligne.modifie_par_id == moi.pk:
                        raise ConflitLigne("Cette valeur a été modifiée entre-temps (peut-être dans un autre onglet) : "
                                           "la nouvelle valeur est affichée.")
                    auteur = ligne.modifie_par.identifiant if ligne.modifie_par else "Quelqu'un"
                    raise ConflitLigne(f"{auteur} vient de modifier cette valeur : la nouvelle valeur est affichée.")

    @transaction.atomic
    def update(self, ligne, donnees):
        ligne = LigneFeuille.objects.select_for_update().get(pk=ligne.pk)   # une écriture à la fois par ligne
        self._verifier_conflit(ligne, donnees.pop('attendu', None))
        avant = self._valeurs_actuelles(ligne)
        # Avancement qui atteint 100 % : statut « Avancement 100 % » (sauf si un statut est choisi en même temps)
        statut_complet = Statut.pour_avancement_complet()
        if (statut_complet and donnees.get('avancement') == 100 and (avant['avancement'] or 0) < 100
                and 'statut' not in donnees):
            donnees['statut'] = statut_complet
        notes = donnees.pop('notes_saisies', None)
        auteur = employe_connecte(self)
        donnees['modifie_par'] = auteur
        ligne = super().update(ligne, donnees)
        for critere_id, note in (notes or {}).items():
            NoteCritere.objects.update_or_create(ligne=ligne, critere_id=critere_id, defaults={'note': note})

        # Historique : une entrée par case réellement modifiée
        criteres = {c.pk: c.numero for c in ligne.feuille.criteres.all()} if notes else {}
        changements = [(c, l, avant[c], getattr(ligne, c)) for c, l in self.LIBELLES.items() if c in donnees]
        changements += [(f'note_{cid}', f'Critère {criteres.get(cid, "?")}', avant.get(f'note_{cid}'), n)
                        for cid, n in (notes or {}).items()]
        # Le statut d'une ligne peut faire apparaître la note de rendement de tout son projet :
        # les autres lignes du projet sont signalées au suivi en direct.
        if 'statut' in donnees and ligne.description_id:
            from django.utils import timezone
            (LigneFeuille.objects.filter(feuille_id=ligne.feuille_id, description__projet_id=ligne.description.projet_id)
             .exclude(pk=ligne.pk).update(modifie_le=timezone.now()))
        HistoriqueLigne.objects.bulk_create([
            HistoriqueLigne(feuille_id=ligne.feuille_id, ligne=ligne, champ=champ, libelle=libelle, auteur=auteur,
                            ancienne_valeur=self._lisible(ancien), nouvelle_valeur=self._lisible(nouveau))
            for champ, libelle, ancien, nouveau in changements if self._brut(ancien) != self._brut(nouveau)
        ])
        return LigneFeuille.objects.select_related(
            'feuille', 'statut', 'statut_controle', 'employe', 'controleur', 'employe_reprise', 'modifie_par',
            'description__projet__affaire', 'description__projet__prestation', 'description__projet__rendement',
        ).prefetch_related('notes', 'parts_pointage__pointage__tache').get(pk=ligne.pk)


class ConflitLigne(APIException):
    """Quelqu'un a modifié la même case entre-temps (réponse 409, code « conflit »)."""
    status_code = 409
    default_code = 'conflit'
    default_detail = "Quelqu'un vient de modifier cette valeur."


class HistoriqueSerializer(serializers.ModelSerializer):
    auteur_details = EmployeResumeSerializer(source='auteur', read_only=True)
    numero_ligne = serializers.IntegerField(source='ligne.numero', read_only=True)
    description = serializers.SerializerMethodField()

    class Meta:
        model = HistoriqueLigne
        fields = ['id', 'ligne', 'numero_ligne', 'description', 'champ', 'libelle', 'ancienne_valeur',
                  'nouvelle_valeur', 'auteur_details', 'date']

    def get_description(self, obj):
        d = obj.ligne.description
        return d.nom if d else obj.ligne.instantane.get('description')
