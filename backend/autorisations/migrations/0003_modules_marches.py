# Conversion des droits des rôles vers les modules détaillés du Marché :
#   « Marchés > Catalogues »        -> Prestations, Tâches, Statuts
#   « Ajouter un marché » (affaires) -> Affaires, et aussi Projets / Communes et Descriptions
#                                      (qu'il couvrait) ; « Supprimer » y passait aux projets et descriptions.
from django.db import migrations

ACTIONS_PROJETS = {'voir', 'creer', 'modifier', 'supprimer', 'exporter'}
ACTIONS_CATALOGUE = {'voir', 'creer', 'modifier', 'supprimer', 'exporter'}


def convertir(apps, schema_editor):
    DroitRole = apps.get_model('autorisations', 'DroitRole')
    for d in list(DroitRole.objects.filter(module__in=['marches_catalogues', 'marches_affaires'])):
        champs = {'role_id': d.role_id, 'effet': d.effet, 'action': d.action, 'perimetre': d.perimetre,
                  'valeur': d.valeur, 'employe_id': d.employe_id, 'affaire_id': d.affaire_id}
        if d.module == 'marches_catalogues':
            DroitRole.objects.create(module='marches_prestations', **champs)
            if d.action in ACTIONS_CATALOGUE:
                for module in ('marches_taches', 'marches_statuts'):
                    DroitRole.objects.create(module=module, **champs)
            d.delete()
        else:   # marches_affaires
            if d.action in ACTIONS_PROJETS:
                for module in ('marches_projets', 'marches_descriptions'):
                    DroitRole.objects.create(module=module, **champs)
            if d.action == 'supprimer':
                d.delete()   # « Supprimer » ne concerne plus l'affaire elle-même (elle s'archive)


class Migration(migrations.Migration):
    dependencies = [('autorisations', '0002_roles')]
    operations = [migrations.RunPython(convertir, migrations.RunPython.noop)]
