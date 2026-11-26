# backend/pointages/serializers.py
from datetime import date as Date

from django.db import transaction
from rest_framework import serializers

from marches.models import Description, Tache
from utilisateurs.serializers import EmployeResumeSerializer

from .models import Pointage
from .services import (ajouter_commentaire, apres_modification, descriptions_pointables, enregistrer_parts,
                       fragment_commentaire, infos_pour_retrait, retirer_de_la_feuille, verifier_chevauchement,
                       verifier_descriptions)


def texte_decimal(valeur):
    return None if valeur is None else str(valeur)


class TacheResumeSerializer(serializers.ModelSerializer):
    type_libelle = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = Tache
        fields = ['id', 'nom', 'type', 'type_libelle', 'plusieurs_descriptions']


class PointageSerializer(serializers.ModelSerializer):
    """
    Écriture : {"date", "heure_debut", "heure_fin", "tache", "descriptions": [id, ...], "commentaire"}
    Plusieurs descriptions : tâche « Plusieurs descriptions », même projet, temps au prorata des quantités.
    """
    employe_details = EmployeResumeSerializer(source='employe', read_only=True)
    tache_details = TacheResumeSerializer(source='tache', read_only=True)
    descriptions = serializers.PrimaryKeyRelatedField(many=True, queryset=Description.objects.all(), write_only=True)
    parts = serializers.SerializerMethodField()
    marche = serializers.SerializerMethodField()

    class Meta:
        model = Pointage
        fields = ['id', 'employe', 'employe_details', 'date', 'heure_debut', 'heure_fin', 'pause', 'tache', 'tache_details',
                  'descriptions', 'parts', 'marche', 'commentaire', 'minutes_normales', 'minutes_hs', 'modifie_le']
        read_only_fields = ['employe', 'minutes_normales', 'minutes_hs']

    def _parts(self, obj):
        return list(obj.parts.all())

    def get_parts(self, obj):
        return [{
            'description_id': p.description_id, 'description': p.description.nom,
            'quantite': texte_decimal(p.description.quantite), 'part': texte_decimal(p.part),
            'minutes': p.minutes_normales + p.minutes_hs,
            'feuille': p.ligne.feuille.nom if p.ligne else None, 'numero_ligne': p.ligne.numero if p.ligne else None,
        } for p in self._parts(obj)]

    def get_marche(self, obj):
        """Colonnes reprises du Marché (une seule description, ou plusieurs du même projet)."""
        parts = self._parts(obj)
        if not parts:
            return {}
        projet = parts[0].description.projet
        quantites = [p.description.quantite for p in parts]
        feuilles = sorted({p.ligne.feuille.nom for p in parts if p.ligne})
        return {
            'affaire_id': projet.affaire_id, 'prestation_id': projet.prestation_id, 'projet_id': projet.id,
            'description_ids': [p.description_id for p in parts],
            'num_affaire': projet.affaire.num_affaire, 'nom_affaire': projet.affaire.nom,
            'prestation': projet.prestation.nom, 'projet': projet.nom,
            'description': ', '.join(p.description.nom for p in parts),
            'quantite': texte_decimal(sum(quantites)) if all(q is not None for q in quantites) else None,
            'unite': projet.prestation.unite,
            'feuille': ', '.join(feuilles) or None,
        }

    def _moi(self):
        """La personne pointée : soi-même, ou celle choisie par un administrateur à l'import (context['employe'])."""
        return self.context.get('employe') or getattr(self.context['request'].user, 'employe', None)

    def validate(self, donnees):
        instance = self.instance
        valeur = lambda champ: donnees.get(champ, getattr(instance, champ, None))
        debut, fin, jour, tache = valeur('heure_debut'), valeur('heure_fin'), valeur('date'), valeur('tache')
        if debut and fin and fin <= debut:
            raise serializers.ValidationError({'heure_fin': "L'heure de fin doit être après l'heure de début."})
        moi = self._moi()
        if moi is None:
            raise serializers.ValidationError('Votre compte n’est relié à aucune fiche employé.')
        if 'descriptions' in donnees or 'tache' in donnees:
            descriptions = donnees.get('descriptions') if 'descriptions' in donnees else \
                [p.description for p in instance.parts.select_related('description')]
            descriptions = list(dict.fromkeys(descriptions))   # sans doublon, dans l'ordre choisi
            autorisees = set(descriptions_pointables(moi).filter(pk__in=[d.pk for d in descriptions]).values_list('pk', flat=True))
            if len(autorisees) != len(descriptions):
                raise serializers.ValidationError({'descriptions': "Une description n'appartient pas à une de vos affaires en cours."})
            verifier_descriptions(descriptions, tache)
            donnees['descriptions'] = descriptions
        verifier_chevauchement(moi, jour, debut, fin, sauf=getattr(instance, 'pk', None))
        if valeur('pause'):
            # Une seule pause par jour
            autre = Pointage.objects.filter(employe=moi, date=jour, pause=True).exclude(pk=getattr(instance, 'pk', None)).first()
            if autre:
                raise serializers.ValidationError({'pause': (
                    f"La pause est déjà cochée sur le pointage {autre.heure_debut:%H:%M}–{autre.heure_fin:%H:%M} de ce jour.")})
            if debut and fin and (fin.hour * 60 + fin.minute) - (debut.hour * 60 + debut.minute) <= 60:
                raise serializers.ValidationError({'pause': 'La pause d’une heure ne peut pas être retirée d’un pointage d’une heure ou moins.'})
        return donnees

    def _ajouter_commentaires(self, pointage):
        """Ajoute le commentaire du pointage dans les feuilles et retient le texte ajouté."""
        fragment = fragment_commentaire(pointage.employe, pointage.date, pointage.commentaire)
        for part in pointage.parts.select_related('ligne'):
            ajouter_commentaire(part.ligne, pointage.tache.type, pointage.employe, fragment)
        if pointage.fragment_commentaire != fragment:
            pointage.fragment_commentaire = fragment
            pointage.save(update_fields=['fragment_commentaire'])

    @transaction.atomic
    def create(self, donnees):
        moi = self._moi()
        descriptions = donnees.pop('descriptions')
        pointage = Pointage.objects.create(employe=moi, **donnees)
        lignes = enregistrer_parts(pointage, descriptions)
        self._ajouter_commentaires(pointage)
        apres_modification([(moi.pk, pointage.date)], lignes)
        return self._relire(pointage)

    @transaction.atomic
    def update(self, pointage, donnees):
        date_avant = pointage.date
        avant = infos_pour_retrait(pointage)
        descriptions = donnees.pop('descriptions', None)
        pointage = super().update(pointage, donnees)
        lignes = set(avant[2])
        if descriptions is not None:
            lignes |= enregistrer_parts(pointage, descriptions)
        # L'ancien commentaire et l'ancienne place sont retirés, puis la version à jour est remise
        pointage.fragment_commentaire = ''
        pointage.save(update_fields=['fragment_commentaire'])
        retirer_de_la_feuille(avant, pointage.employe)
        self._ajouter_commentaires(pointage)
        apres_modification([(pointage.employe_id, date_avant), (pointage.employe_id, pointage.date)], lignes)
        return self._relire(pointage)

    @staticmethod
    def _relire(pointage):
        return (Pointage.objects.select_related('employe', 'tache')
                .prefetch_related('parts__description__projet__affaire', 'parts__description__projet__prestation',
                                  'parts__ligne__feuille')
                .get(pk=pointage.pk))
