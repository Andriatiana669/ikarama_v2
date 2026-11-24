# backend/notifications/management/commands/envoyer_rappels.py
"""
Rappels de pointage incomplet (notification dans l'application ; l'e-mail part avec le récapitulatif du soir).

  python manage.py envoyer_rappels --veille     chaque matin : le dernier jour ouvrable avant aujourd'hui
  python manage.py envoyer_rappels --semaine    chaque vendredi : la semaine en cours jusqu'à aujourd'hui
  Options : --simulation (affiche sans rien créer), --date AAAA-MM-JJ (jour de référence, pour essayer).

Personnes concernées : celles qui ont accès au site et sont responsables ou membres d'au moins une affaire en cours.
"""
from datetime import date as Date
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from autorisations.acces import q_acces
from notifications.services import notifier
from pointages.erreurs import erreurs_pointage
from utilisateurs.models import Employe


def personnes_concernees():
    return (Employe.objects.filter(q_acces())
            .filter(Q(affaires_responsable__actif=True) | Q(affaires_membre__actif=True)).distinct())


def jour_ouvrable_precedent(jour):
    jour -= timedelta(days=1)
    while jour.weekday() > 4:
        jour -= timedelta(days=1)
    return jour


class Command(BaseCommand):
    help = 'Crée les rappels de pointage incomplet (veille ou semaine).'

    def add_arguments(self, parser):
        groupe = parser.add_mutually_exclusive_group(required=True)
        groupe.add_argument('--veille', action='store_true', help='Le dernier jour ouvrable avant aujourd’hui.')
        groupe.add_argument('--semaine', action='store_true', help='La semaine en cours jusqu’à aujourd’hui.')
        parser.add_argument('--simulation', action='store_true', help='Affiche les rappels sans les créer.')
        parser.add_argument('--date', help='Jour de référence AAAA-MM-JJ (par défaut aujourd’hui).')

    def handle(self, *args, **options):
        try:
            aujourd_hui = Date.fromisoformat(options['date']) if options['date'] else Date.today()
        except ValueError:
            raise CommandError('Date invalide (AAAA-MM-JJ).')
        if options['veille']:
            debut = fin = jour_ouvrable_precedent(aujourd_hui)
            titre = f"Pointage incomplet du {debut:%d/%m/%Y}"
            cle = f'rappel-{debut.isoformat()}'
        else:
            debut = aujourd_hui - timedelta(days=aujourd_hui.weekday())
            fin = min(debut + timedelta(days=4), aujourd_hui)
            titre = f"Pointage de la semaine du {debut:%d/%m} incomplet"
            cle = f'rappel-semaine-{debut.isoformat()}'

        total = 0
        for employe in personnes_concernees():
            erreurs = erreurs_pointage(employe, debut, fin, jusqu_a=fin)
            if not erreurs:
                continue
            total += 1
            message = '\n'.join(e['message'] for e in erreurs)
            if options['simulation']:
                self.stdout.write(f'{employe.identifiant} : {message.replace(chr(10), " ; ")}')
            else:
                notifier([employe], 'rappel_pointage', titre, message=message, lien='/pointages/mon-temps', cle=cle)
        verbe = 'à prévenir (simulation)' if options['simulation'] else 'prévenue(s)'
        self.stdout.write(self.style.SUCCESS(f'{total} personne(s) {verbe} pour {debut:%d/%m/%Y}' +
                                             (f' au {fin:%d/%m/%Y}' if fin != debut else '') + '.'))
