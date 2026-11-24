# backend/notifications/management/commands/envoyer_recapitulatif.py
"""
E-mail récapitulatif quotidien : un seul e-mail par personne, avec ses notifications non lues pas encore envoyées.

  python manage.py envoyer_recapitulatif               (à planifier une fois par jour, par exemple à 17h)
  python manage.py envoyer_recapitulatif --simulation  affiche ce qui serait envoyé, sans rien envoyer

Réglages : EMAIL_HOST, EMAIL_PORT, EMAIL_USE_TLS, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, DEFAULT_FROM_EMAIL,
URL_APPLICATION (adresse de l'application pour les liens). Sans EMAIL_HOST, les e-mails s'affichent dans la console.
"""
from collections import defaultdict
from html import escape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand

from notifications.models import Notification


class Command(BaseCommand):
    help = 'Envoie l’e-mail récapitulatif des notifications non lues.'

    def add_arguments(self, parser):
        parser.add_argument('--simulation', action='store_true', help='Affiche sans envoyer.')

    def handle(self, *args, **options):
        a_envoyer = (Notification.objects.filter(lu=False, envoyee_par_email=False)
                     .select_related('destinataire').order_by('destinataire_id', 'cree_le'))
        par_personne = defaultdict(list)
        for n in a_envoyer:
            par_personne[n.destinataire].append(n)

        envoyes, sans_adresse, echecs = 0, 0, 0
        for employe, notifications in par_personne.items():
            adresse = (getattr(employe, 'email', '') or '').strip()
            if not adresse:
                sans_adresse += 1
                continue
            sujet = f"Ikarama : {len(notifications)} notification(s) à lire"
            lignes_texte, lignes_html = [], []
            for n in notifications:
                lien = f"{settings.URL_APPLICATION}{n.lien}" if n.lien else settings.URL_APPLICATION
                lignes_texte.append(f"- {n.titre}\n  {n.message}\n  {lien}".rstrip())
                lignes_html.append(
                    f'<li style="margin-bottom:10px"><a href="{escape(lien)}" style="color:#18355d;font-weight:bold">{escape(n.titre)}</a>'
                    f'<br><span style="color:#5a677a;white-space:pre-line">{escape(n.message)}</span></li>')
            texte = (f"Bonjour {employe.prenom_usuel or employe.prenom},\n\nVoici vos notifications non lues :\n\n"
                     + '\n\n'.join(lignes_texte) + f"\n\nOuvrir Ikarama : {settings.URL_APPLICATION}\n")
            html = (f'<div style="font-family:Arial,sans-serif;color:#1f2937"><p>Bonjour {escape(employe.prenom_usuel or employe.prenom or "")},</p>'
                    f'<p>Voici vos notifications non lues :</p><ul>{"".join(lignes_html)}</ul>'
                    f'<p><a href="{escape(settings.URL_APPLICATION)}" style="color:#e94242">Ouvrir Ikarama</a></p></div>')
            if options['simulation']:
                self.stdout.write(f'À {adresse} : {sujet}')
                continue
            try:
                message = EmailMultiAlternatives(sujet, texte, settings.DEFAULT_FROM_EMAIL, [adresse])
                message.attach_alternative(html, 'text/html')
                message.send()
            except Exception as erreur:   # un envoi raté n'empêche pas les autres
                echecs += 1
                self.stderr.write(f'Échec pour {employe.identifiant} : {erreur}')
                continue
            Notification.objects.filter(pk__in=[n.pk for n in notifications]).update(envoyee_par_email=True)
            envoyes += 1
        self.stdout.write(self.style.SUCCESS(
            f'{envoyes} e-mail(s) envoyé(s), {sans_adresse} personne(s) sans adresse, {echecs} échec(s)'
            + (' (simulation)' if options['simulation'] else '') + '.'))
