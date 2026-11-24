# Un pointage est désormais rattaché à une Description du Marché ; la ligne de feuille devient facultative.
# Reprise : chaque pointage existant prend la description de sa ligne.
import django.db.models.deletion
from django.db import migrations, models


def remplir_description(apps, schema_editor):
    Pointage = apps.get_model('pointages', 'Pointage')
    for pointage in Pointage.objects.select_related('ligne').filter(description__isnull=True):
        pointage.description_id = pointage.ligne.description_id
        pointage.save(update_fields=['description'])


class Migration(migrations.Migration):

    dependencies = [
        ('pointages', '0001_initial'),
        ('marches', '0006_tache_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='pointage', name='description',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='pointages', to='marches.description'),
        ),
        migrations.RunPython(remplir_description, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='pointage', name='description',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pointages',
                                    to='marches.description'),
        ),
        migrations.AlterField(
            model_name='pointage', name='ligne',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='pointages', to='gsheets.lignefeuille'),
        ),
    ]
