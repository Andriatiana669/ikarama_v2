# Les rôles qui voyaient la Durée estimatif par « Projets / Communes > Voir » la gardent (nouveau module).
from django.db import migrations


def reprendre(apps, schema_editor):
    DroitRole = apps.get_model('autorisations', 'DroitRole')
    for d in DroitRole.objects.filter(module='marches_projets', action__in=['voir', 'exporter']):
        DroitRole.objects.create(role_id=d.role_id, effet=d.effet, module='marches_duree', action=d.action,
                                 perimetre=d.perimetre, valeur=d.valeur, employe_id=d.employe_id, affaire_id=d.affaire_id)


class Migration(migrations.Migration):
    dependencies = [('autorisations', '0003_modules_marches')]
    operations = [migrations.RunPython(reprendre, migrations.RunPython.noop)]
