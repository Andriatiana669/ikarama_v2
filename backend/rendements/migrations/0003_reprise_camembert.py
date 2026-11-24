# Les tâches cochées « Dans le camembert du temps » (Marchés > Tâches) passent dans Paramètres > Graphiques.
from django.db import migrations


def reprendre(apps, schema_editor):
    Tache = apps.get_model('marches', 'Tache')
    Parametres = apps.get_model('rendements', 'ParametresGraphiques')
    parametres, _ = Parametres.objects.get_or_create(pk=1)
    parametres.taches_camembert.set(Tache.objects.filter(camembert_temps=True))


class Migration(migrations.Migration):

    dependencies = [
        ('rendements', '0002_parametres_graphiques'),
        ('marches', '0011_tache_camembert_temps'),
    ]

    operations = [migrations.RunPython(reprendre, migrations.RunPython.noop)]
