# Les descriptions ne forment plus un catalogue commun : chacune appartient à un Projet / Commune,
# avec sa quantité. La quantité du projet devient la somme des quantités de ses descriptions.
#
# Reprise des données : chaque description cochée pour un projet devient une description de ce projet
# (une copie par projet si elle était cochée pour plusieurs). Les descriptions du catalogue qui n'étaient
# cochées pour aucun projet sont supprimées. Les quantités déjà saisies sur les projets sont conservées.
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def convertir(apps, schema_editor):
    Description = apps.get_model('marches', 'Description')
    Lien = apps.get_model('marches', 'ProjetDescription')

    for description in list(Description.objects.all()):
        liens = list(Lien.objects.filter(description=description).order_by('id'))
        if not liens:
            description.delete()
            continue
        for index, lien in enumerate(liens):
            cible = description if index == 0 else Description(nom=description.nom, cree_par_id=description.cree_par_id)
            cible.projet_id = lien.projet_id
            cible.save()

    # Numéros et ordre : 1, 2, 3… dans chaque projet
    for projet_id in set(Description.objects.values_list('projet_id', flat=True)):
        for numero, description in enumerate(Description.objects.filter(projet_id=projet_id).order_by('ordre', 'id'), 1):
            description.numero = description.ordre = numero
            description.save(update_fields=['numero', 'ordre'])


class Migration(migrations.Migration):

    dependencies = [
        ('marches', '0002_statuts'),
    ]

    operations = [
        migrations.AddField(
            model_name='description', name='projet',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='marches.projet'),
        ),
        migrations.AddField(
            model_name='description', name='numero',
            field=models.PositiveIntegerField(default=0, editable=False, verbose_name='ID'),
        ),
        migrations.AddField(
            model_name='description', name='quantite',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True, verbose_name='quantité'),
        ),
        migrations.AlterField(
            model_name='description', name='nom',
            field=models.CharField(max_length=200, verbose_name='description'),
        ),
        migrations.RunPython(convertir, migrations.RunPython.noop),
        migrations.RemoveField(model_name='projet', name='descriptions'),
        migrations.DeleteModel(name='ProjetDescription'),
        migrations.AlterField(
            model_name='description', name='projet',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='descriptions', to='marches.projet'),
        ),
        migrations.AlterField(
            model_name='description', name='numero',
            field=models.PositiveIntegerField(editable=False, help_text='Numéro dans le projet : 1, 2, 3… (jamais réutilisé)', verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='projet', name='quantite',
            field=models.DecimalField(blank=True, decimal_places=2, editable=False, max_digits=14, null=True, verbose_name='quantité'),
        ),
        migrations.AddConstraint(
            model_name='description',
            constraint=models.UniqueConstraint(fields=('projet', 'numero'), name='numero_description_unique_par_projet'),
        ),
        migrations.AddConstraint(
            model_name='description',
            constraint=models.UniqueConstraint(fields=('projet', 'nom'), name='description_unique_par_projet',
                                               violation_error_message='Ce projet a déjà une description de ce nom.'),
        ),
        migrations.AddField(
            model_name='statut', name='couleur',
            field=models.CharField(default='#E8EEF6', max_length=7, verbose_name='couleur de fond',
                                   validators=[django.core.validators.RegexValidator('^#[0-9A-Fa-f]{6}$', 'Couleur attendue au format #RRGGBB.')]),
        ),
    ]
