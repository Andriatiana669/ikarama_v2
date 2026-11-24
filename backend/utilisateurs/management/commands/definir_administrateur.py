# backend/utilisateurs/management/commands/definir_administrateur.py
"""
Donne (ou retire) les droits d'administrateur Ikarama à un employé, par son matricule.

    python manage.py definir_administrateur PR00123
    python manage.py definir_administrateur PR00123 --retirer

Administrateur = compte Django « superuser » + « staff » : accès à tout Ikarama
et à l'administration Django (/admin/). Même principe qu'Alimanaka.
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from utilisateurs.models import Employe


class Command(BaseCommand):
    help = "Donne ou retire les droits d'administrateur à un employé (par matricule)."

    def add_arguments(self, parser):
        parser.add_argument('matricule', help='Matricule (code-barre), ex. PR00123')
        parser.add_argument('--retirer', action='store_true', help='Retirer les droits au lieu de les donner')

    def handle(self, matricule, retirer=False, **options):
        matricule = matricule.strip().upper()
        employe = Employe.objects.select_related('user').filter(code_barre__iexact=matricule).first()
        user = (employe.user if employe and employe.user
                else User.objects.filter(username__iexact=matricule).first())

        if user is None:
            if retirer:
                raise CommandError(f"Aucun compte pour {matricule}.")
            # La personne ne s'est jamais connectée : on prépare son compte
            user = User(username=matricule)
            user.set_unusable_password()
            user.save()
            if employe and not employe.user_id:
                employe.user = user
                employe.save(update_fields=['user'])
            self.stdout.write(f"Compte {matricule} créé (il sera utilisé à sa première connexion).")

        user.is_superuser = user.is_staff = not retirer
        user.save(update_fields=['is_superuser', 'is_staff'])
        etat = 'retirés à' if retirer else 'donnés à'
        self.stdout.write(self.style.SUCCESS(f"Droits d'administrateur {etat} {user.username}."))
