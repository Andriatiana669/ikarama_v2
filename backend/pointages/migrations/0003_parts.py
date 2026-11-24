# Un pointage peut viser plusieurs descriptions : la description et la ligne passent dans PartPointage.
# Reprise : chaque pointage existant reçoit une part unique (100 %) avec sa description et sa ligne.
import django.db.models.deletion
from django.db import migrations, models


def creer_parts(apps, schema_editor):
    Pointage = apps.get_model('pointages', 'Pointage')
    PartPointage = apps.get_model('pointages', 'PartPointage')
    PartPointage.objects.bulk_create([
        PartPointage(pointage=p, description_id=p.description_id, ligne_id=p.ligne_id, part=1,
                     minutes_normales=p.minutes_normales, minutes_hs=p.minutes_hs)
        for p in Pointage.objects.all()
    ])


class Migration(migrations.Migration):

    dependencies = [
        ('pointages', '0002_pointage_description'),
        ('marches', '0008_tache_plusieurs_descriptions'),
        ('gsheets', '0004_commentaires_controle_reprise'),
    ]

    operations = [
        migrations.CreateModel(
            name='PartPointage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('part', models.DecimalField(decimal_places=6, default=1, help_text='Entre 0 et 1, figée au pointage', max_digits=7)),
                ('minutes_normales', models.PositiveIntegerField(default=0, editable=False)),
                ('minutes_hs', models.PositiveIntegerField(default=0, editable=False)),
                ('description', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='parts_pointage', to='marches.description')),
                ('ligne', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='parts_pointage', to='gsheets.lignefeuille')),
                ('pointage', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parts', to='pointages.pointage')),
            ],
            options={
                'verbose_name': 'pointage',
                'verbose_name_plural': 'pointages',
                'ordering': ['id'],
                'constraints': [models.UniqueConstraint(fields=('pointage', 'description'), name='part_description_unique')],
            },
        ),
        migrations.RunPython(creer_parts, migrations.RunPython.noop),
        migrations.RemoveField(model_name='pointage', name='description'),
        migrations.RemoveField(model_name='pointage', name='ligne'),
    ]
