# backend/marches/serializers.py
from decimal import Decimal, InvalidOperation

from django.db import transaction
from rest_framework import serializers

from autorisations.acces import q_visible
from utilisateurs.models import Employe
from utilisateurs.serializers import EmployeResumeSerializer

from .models import Affaire, Description, Prestation, Projet, RendementObjectif, Statut, Tache
from .suivi import SuiviMixin


class AuteurMixin(serializers.Serializer):
    cree_par_details = EmployeResumeSerializer(source='cree_par', read_only=True)


# ------------------------------------------------------------------
# Catalogues
# ------------------------------------------------------------------
class RendementSerializer(serializers.ModelSerializer):
    class Meta:
        model = RendementObjectif
        fields = ['id', 'valeur']


class PrestationSerializer(SuiviMixin, AuteurMixin, serializers.ModelSerializer):
    niveau_suivi = 'prestation'   # dans l'affaire de ?affaire=
    # Lecture : [{"id": 3, "valeur": "120.00"}, ...]  ·  Écriture : [120, 80.5]
    rendements = RendementSerializer(many=True, read_only=True)
    statut = serializers.SerializerMethodField()
    valeurs_rendement = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    temps = serializers.SerializerMethodField()
    cochee = serializers.BooleanField(read_only=True, required=False)   # quand ?affaire= est fourni
    nb_projets = serializers.IntegerField(read_only=True, required=False)
    # Temps d'une tâche choisie dans la page (?tache=<id>)
    temps_tache = serializers.SerializerMethodField()

    class Meta:
        model = Prestation
        fields = ['id', 'nom', 'unite', 'rendements', 'valeurs_rendement', 'temps', 'temps_tache', 'statut', 'cochee', 'nb_projets',
                  'cree_par_details', 'cree_le']

    def get_temps(self, obj):
        return super().get_temps(obj) if self._affaire_suivi() else None   # sans affaire : pas de sens

    def get_temps_tache(self, obj):
        return super().get_temps_tache(obj) if self._affaire_suivi() else None

    def get_statut(self, obj):
        return self.get_statut_suivi(obj) if self._affaire_suivi() else None

    def validate_valeurs_rendement(self, valeurs):
        nombres = []
        for v in valeurs:
            try:
                nombre = Decimal(str(v).replace(',', '.').strip())
            except InvalidOperation:
                raise serializers.ValidationError(f"« {v} » n'est pas un nombre.")
            if nombre <= 0:
                raise serializers.ValidationError('Les rendements doivent être supérieurs à 0.')
            if nombre not in nombres:
                nombres.append(nombre)
        if not nombres:
            raise serializers.ValidationError('Indiquez au moins un rendement objectif par jour.')
        return nombres

    def validate(self, donnees):
        if self.instance is None and 'valeurs_rendement' not in donnees:
            raise serializers.ValidationError({'valeurs_rendement': 'Indiquez au moins un rendement objectif par jour.'})
        return donnees

    def _enregistrer_rendements(self, prestation, valeurs):
        actuels = {r.valeur: r for r in prestation.rendements.all()}
        for valeur, rendement in actuels.items():
            if valeur not in valeurs:
                if rendement.projets.exists():
                    raise serializers.ValidationError({'valeurs_rendement': [
                        f"Le rendement {valeur.normalize():f} est utilisé par un projet : il ne peut pas être retiré."]})
                rendement.delete()
        for position, valeur in enumerate(valeurs, start=1):
            rendement = actuels.get(valeur) or RendementObjectif(prestation=prestation, valeur=valeur)
            rendement.ordre = position
            rendement.save()

    @transaction.atomic
    def create(self, donnees):
        valeurs = donnees.pop('valeurs_rendement')
        prestation = super().create(donnees)
        self._enregistrer_rendements(prestation, valeurs)
        return prestation

    @transaction.atomic
    def update(self, instance, donnees):
        valeurs = donnees.pop('valeurs_rendement', None)
        prestation = super().update(instance, donnees)
        if valeurs is not None:
            self._enregistrer_rendements(prestation, valeurs)
        return prestation


class TacheSerializer(AuteurMixin, serializers.ModelSerializer):
    type_libelle = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = Tache
        fields = ['id', 'nom', 'type', 'type_libelle', 'plusieurs_descriptions', 'temps_projet', 'cree_par_details', 'cree_le']


class StatutSerializer(AuteurMixin, serializers.ModelSerializer):
    class Meta:
        model = Statut
        fields = ['id', 'nom', 'couleur', 'par_defaut', 'prioritaire_pointage', 'active_note_rendement',
                  'avancement_complet', 'en_train_de_faire', 'cree_par_details', 'cree_le']

    def validate_couleur(self, valeur):
        return valeur.upper()


# ------------------------------------------------------------------
# Affaires et projets
# ------------------------------------------------------------------
class PersonnesField(serializers.PrimaryKeyRelatedField):
    """Liste d'employés, choisis parmi les personnes visibles (règles d'accès au site)."""

    def get_queryset(self):
        return Employe.objects.filter(q_visible())


class AffaireSerializer(SuiviMixin, AuteurMixin, serializers.ModelSerializer):
    niveau_suivi = 'affaire'
    responsables = PersonnesField(many=True, allow_empty=False)
    membres = PersonnesField(many=True, allow_empty=False)
    responsables_details = EmployeResumeSerializer(source='responsables', many=True, read_only=True)
    membres_details = EmployeResumeSerializer(source='membres', many=True, read_only=True)
    nb_prestations = serializers.IntegerField(read_only=True, required=False)
    temps = serializers.SerializerMethodField()
    statut = serializers.SerializerMethodField()
    # RESPONSABLE | MEMBRE | null : rôle de la personne connectée dans l'affaire
    mon_role = serializers.SerializerMethodField()
    # Temps d'une tâche choisie dans la page (?tache=<id>)
    temps_tache = serializers.SerializerMethodField()

    class Meta:
        model = Affaire
        fields = ['id', 'num_affaire', 'nom', 'temps', 'temps_tache', 'statut', 'responsables', 'responsables_details',
                  'membres', 'membres_details', 'nb_prestations', 'mon_role', 'actif', 'cree_par_details',
                  'cree_le', 'modifie_le', 'pointage_seul']
        extra_kwargs = {'actif': {'read_only': True}}

    def get_statut(self, obj):
        return self.get_statut_suivi(obj)

    def get_mon_role(self, obj):
        request = self.context.get('request')
        moi = getattr(getattr(request, 'user', None), 'employe', None)
        if moi is None:
            return None
        if any(p.pk == moi.pk for p in obj.responsables.all()):   # listes déjà préchargées
            return 'RESPONSABLE'
        if any(p.pk == moi.pk for p in obj.membres.all()):
            return 'MEMBRE'
        return None

    def validate_num_affaire(self, valeur):
        return (valeur or '').strip()   # facultatif, et plusieurs affaires peuvent avoir le même n°


class ProjetSerializer(SuiviMixin, AuteurMixin, serializers.ModelSerializer):
    niveau_suivi = 'projet'
    rendement_valeur = serializers.DecimalField(source='rendement.valeur', max_digits=12, decimal_places=2, read_only=True)
    unite = serializers.CharField(source='prestation.unite', read_only=True)
    prestation_nom = serializers.CharField(source='prestation.nom', read_only=True)
    nb_descriptions = serializers.IntegerField(read_only=True, required=False)
    temps = serializers.SerializerMethodField()
    statut = serializers.SerializerMethodField()
    # Temps d'une tâche choisie dans la page (?tache=<id>)
    temps_tache = serializers.SerializerMethodField()

    class Meta:
        model = Projet
        fields = ['id', 'numero', 'affaire', 'prestation', 'prestation_nom', 'nom', 'quantite', 'unite',
                  'rendement', 'rendement_valeur', 'date_livraison', 'temps', 'temps_tache', 'statut', 'nb_descriptions',
                  'cree_par_details', 'cree_le']
        # La quantité est la somme des quantités des descriptions : jamais saisie directement
        read_only_fields = ['numero', 'quantite']

    def get_statut(self, obj):
        return self.get_statut_suivi(obj)

    def validate(self, donnees):
        if self.instance is not None:
            # Un projet ne change pas d'affaire ni de prestation
            donnees.pop('affaire', None)
            donnees.pop('prestation', None)
        return donnees

    @transaction.atomic
    def create(self, donnees):
        # Verrou sur l'affaire : deux créations simultanées n'obtiennent pas le même numéro
        Affaire.objects.select_for_update().filter(pk=donnees['affaire'].pk).first()
        return super().create(donnees)


class DescriptionSerializer(SuiviMixin, AuteurMixin, serializers.ModelSerializer):
    niveau_suivi = 'description'
    unite = serializers.CharField(source='projet.prestation.unite', read_only=True)
    temps = serializers.SerializerMethodField()
    statut = serializers.SerializerMethodField()

    class Meta:
        model = Description
        fields = ['id', 'numero', 'projet', 'nom', 'quantite', 'unite', 'temps', 'statut',
                  'cree_par_details', 'cree_le']
        read_only_fields = ['numero']

    def get_statut(self, obj):
        return self.get_statut_suivi(obj)

    def validate_quantite(self, valeur):
        if valeur is not None and valeur < 0:
            raise serializers.ValidationError('La quantité ne peut pas être négative.')
        return valeur

    def validate(self, donnees):
        if self.instance is not None:
            donnees.pop('projet', None)   # une description ne change pas de projet
        return donnees

    @transaction.atomic
    def create(self, donnees):
        # Verrou sur le projet : deux créations simultanées n'obtiennent pas le même numéro
        Projet.objects.select_for_update().filter(pk=donnees['projet'].pk).first()
        return super().create(donnees)
