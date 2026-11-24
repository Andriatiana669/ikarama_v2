# Le statut « en train de faire » devient un rôle du statut (Marchés > Statuts) : on reprend le choix existant.
from django.db import migrations


def reprendre(apps, schema_editor):
    Parametres = apps.get_model('planning', 'ParametresPlanning')
    Statut = apps.get_model('marches', 'Statut')
    p = Parametres.objects.filter(pk=1).first()
    if p and p.statut_en_cours_id and not Statut.objects.filter(en_train_de_faire=True).exists():
        Statut.objects.filter(pk=p.statut_en_cours_id).update(en_train_de_faire=True)


class Migration(migrations.Migration):
    dependencies = [('planning', '0001_initial'), ('marches', '0013_statut_en_train_de_faire')]
    operations = [
        migrations.RunPython(reprendre, migrations.RunPython.noop),
        migrations.DeleteModel(name='ParametresPlanning'),
    ]
