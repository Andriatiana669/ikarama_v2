# Date de début des lignes : première date pointée pour leur DESCRIPTION (et non plus seulement
# les pointages rattachés à la ligne), pour compter aussi ceux faits avant la création de la feuille.
from django.db import migrations
from django.db.models import Min


def recalculer(apps, schema_editor):
    LigneFeuille = apps.get_model('gsheets', 'LigneFeuille')
    PartPointage = apps.get_model('pointages', 'PartPointage')
    dates = dict(PartPointage.objects.values_list('description_id').annotate(d=Min('pointage__date')))
    for ligne in LigneFeuille.objects.exclude(description__isnull=True):
        date = dates.get(ligne.description_id)
        if ligne.date_debut != date:
            ligne.date_debut = date
            ligne.save(update_fields=['date_debut'])


class Migration(migrations.Migration):

    dependencies = [
        ('pointages', '0005_date_debut_des_lignes'),
    ]

    operations = [migrations.RunPython(recalculer, migrations.RunPython.noop)]
