# La case « Camembert » quitte les tâches : elle est désormais dans Paramètres > Graphiques.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('marches', '0011_tache_camembert_temps'),
        ('rendements', '0003_reprise_camembert'),
    ]

    operations = [migrations.RemoveField(model_name='tache', name='camembert_temps')]
