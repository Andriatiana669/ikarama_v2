# Pause : case « Pause (−1 h) » cochée par la personne sur un pointage de la journée.
#  1. Ajoute la case.
#  2. Reprise : la case est cochée sur le pointage qui couvre entièrement 12h00–13h00 (journée pointée
#     d'un seul tenant) ; les autres jours ouvrables pointés apparaîtront en « pause non cochée ».
#  3. Recalcule H_Durée / HS de tous les pointages, leur partage entre descriptions, puis les temps
#     des lignes de feuille.
from datetime import time
from decimal import Decimal

from django.db import migrations, models
from django.db.models import F, Sum

TYPES = {'PRODUCTION': 'temps_prod', 'CONTROLE': 'temps_controle', 'REPRISE': 'temps_reprise'}


def minutes(t):
    return t.hour * 60 + t.minute


def calculer(jour, debut, fin, pause):
    # Copie de la règle (une migration ne doit pas dépendre du code qui évolue)
    d, f = minutes(debut), minutes(fin)
    normales = max(0, min(f, 16 * 60 + 30) - max(d, 7 * 60 + 30)) if jour.weekday() < 5 else 0
    hs = (f - d) - normales
    if pause:
        retrait = min(60, normales)
        normales -= retrait
        hs -= min(60 - retrait, hs)
    return normales, hs


def repartir(total, parts):
    bruts = [Decimal(total) * p for p in parts]
    entiers = [int(b) for b in bruts]
    for i in sorted(range(len(parts)), key=lambda i: bruts[i] - entiers[i], reverse=True)[:total - sum(entiers)]:
        entiers[i] += 1
    return entiers


def reprendre(apps, schema_editor):
    Pointage = apps.get_model('pointages', 'Pointage')
    PartPointage = apps.get_model('pointages', 'PartPointage')
    LigneFeuille = apps.get_model('gsheets', 'LigneFeuille')

    # 2. Pause cochée sur le pointage qui couvre midi (un seul par jour et par personne)
    deja = set()
    for p in Pointage.objects.filter(heure_debut__lte=time(12, 0), heure_fin__gte=time(13, 0)).order_by('date', 'heure_debut'):
        if p.date.weekday() < 5 and (p.employe_id, p.date) not in deja:
            deja.add((p.employe_id, p.date))
            p.pause = True
            p.save(update_fields=['pause'])

    # 3. Recalcul
    lignes = set()
    for p in Pointage.objects.all():
        normales, hs = calculer(p.date, p.heure_debut, p.heure_fin, p.pause)
        if (p.minutes_normales, p.minutes_hs) != (normales, hs):
            p.minutes_normales, p.minutes_hs = normales, hs
            p.save(update_fields=['minutes_normales', 'minutes_hs'])
        parts = list(PartPointage.objects.filter(pointage=p).order_by('id'))
        coefficients = [part.part for part in parts]
        for part, n, h in zip(parts, repartir(normales, coefficients), repartir(hs, coefficients)):
            part.minutes_normales, part.minutes_hs = n, h
            part.save(update_fields=['minutes_normales', 'minutes_hs'])
            if part.ligne_id:
                lignes.add(part.ligne_id)

    for ligne in LigneFeuille.objects.filter(pk__in=lignes):
        for type_tache, champ in TYPES.items():
            parts = PartPointage.objects.filter(ligne=ligne, pointage__tache__type=type_tache)
            if parts.exists():
                total = parts.aggregate(t=Sum(F('minutes_normales') + F('minutes_hs')))['t'] or 0
                setattr(ligne, champ, (Decimal(total) / 60).quantize(Decimal('0.01')))
            else:
                setattr(ligne, champ, None)
        ligne.save(update_fields=list(TYPES.values()))


class Migration(migrations.Migration):

    dependencies = [
        ('pointages', '0006_date_debut_par_description'),
        ('gsheets', '0004_commentaires_controle_reprise'),
    ]

    operations = [
        migrations.AddField(
            model_name='pointage', name='pause',
            field=models.BooleanField(default=False, verbose_name='pause (−1 h)'),
        ),
        migrations.RunPython(reprendre, migrations.RunPython.noop),
    ]
