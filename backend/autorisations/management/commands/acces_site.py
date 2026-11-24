# backend/autorisations/management/commands/acces_site.py
"""
Gestion de secours des règles d'accès au site, en ligne de commande.

    python manage.py acces_site                      # liste les règles et l'état
    python manage.py acces_site --verifier PR00123   # cette personne a-t-elle accès ?
    python manage.py acces_site --autoriser PR00123  # ajoute une règle « Autoriser » pour cette personne
    python manage.py acces_site --tout-desactiver    # désactive toutes les règles : site ouvert à tous
"""
from django.core.management.base import BaseCommand, CommandError

from autorisations import acces
from autorisations.models import RegleAcces
from utilisateurs.models import Employe


class Command(BaseCommand):
    help = "Affiche ou corrige les règles d'accès au site (secours)."

    def add_arguments(self, parser):
        groupe = parser.add_mutually_exclusive_group()
        groupe.add_argument('--verifier', metavar='MATRICULE')
        groupe.add_argument('--autoriser', metavar='MATRICULE')
        groupe.add_argument('--tout-desactiver', action='store_true')

    def employe(self, matricule):
        employe = Employe.objects.filter(code_barre__iexact=matricule.strip()).first()
        if not employe:
            raise CommandError(f"Aucun employé avec le matricule {matricule}.")
        return employe

    def handle(self, verifier=None, autoriser=None, tout_desactiver=False, **options):
        if tout_desactiver:
            n = RegleAcces.objects.filter(actif=True).update(actif=False)
            acces.invalider()
            self.stdout.write(self.style.WARNING(f"{n} règle(s) désactivée(s) : le site est ouvert à tous."))
            return
        if autoriser:
            employe = self.employe(autoriser)
            RegleAcces.objects.create(effet='AUTORISER', critere='MATRICULE', employe=employe,
                                      commentaire='Ajoutée en ligne de commande')
            # Un refus l'emporte : on prévient s'il en reste un
            if not acces.a_acces(employe):
                self.stdout.write(self.style.WARNING("Règle ajoutée, mais une règle « Refuser » bloque encore cette personne."))
            else:
                self.stdout.write(self.style.SUCCESS(f"{employe.identifiant} a maintenant accès au site."))
            return
        if verifier:
            employe = self.employe(verifier)
            resultat = acces.expliquer(employe)
            self.stdout.write(f"{employe.identifiant} : {'ACCÈS AUTORISÉ' if resultat['acces'] else 'ACCÈS REFUSÉ'}")
            for regle in resultat['regles']:
                self.stdout.write(f"  - {regle['effet']} : {regle['description']}")
            return

        etat = acces.etat()
        self.stdout.write('Mode : ' + ('OUVERT (aucune règle « Autoriser »)' if etat['ouvert'] else 'RESTREINT'))
        for regle in RegleAcces.objects.select_related('employe'):
            self.stdout.write(f"  [{'actif' if regle.actif else 'inactif'}] #{regle.pk} {regle}")
