# Date de début des lignes de feuille : premier jour pointé (reprise des pointages existants).
from django.db import migrations
from django.db.models import Min


def remplir(apps, schema_editor):
    LigneFeuille = apps.get_model('gsheets', 'LigneFeuille')
    PartPointage = apps.get_model('pointages', 'PartPointage')
    premiers = (PartPointage.objects.exclude(ligne__isnull=True).values('ligne_id')
                .annotate(d=Min('pointage__date')))
    for p in premiers:
        LigneFeuille.objects.filter(pk=p['ligne_id']).update(date_debut=p['d'])


class Migration(migrations.Migration):

    dependencies = [
        ('pointages', '0004_fragment_commentaire'),
        ('gsheets', '0004_commentaires_controle_reprise'),
    ]

    operations = [migrations.RunPython(remplir, migrations.RunPython.noop)]
