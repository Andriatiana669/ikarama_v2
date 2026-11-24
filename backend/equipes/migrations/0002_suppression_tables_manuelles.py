# Les équipes sont désormais calculées depuis les fiches employés (API RH) :
# suppression des tables saisies à la main (directions, pôles, équipes, membres, historique).
# ATTENTION : les données de ces tables sont définitivement effacées par `migrate`.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('equipes', '0001_initial'),
    ]

    operations = [
        # Ordre : d'abord les tables qui pointent vers les autres
        migrations.DeleteModel(name='HistoriqueMouvementEquipe'),
        migrations.DeleteModel(name='MembreEquipe'),
        migrations.DeleteModel(name='Equipe'),
        migrations.DeleteModel(name='Pole'),
        migrations.DeleteModel(name='Direction'),
    ]
