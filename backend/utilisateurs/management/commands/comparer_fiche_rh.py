# backend/utilisateurs/management/commands/comparer_fiche_rh.py
"""
Compare la fiche d'un employé dans Ikarama avec ce que renvoie l'API RH en ce moment.
Lecture seule : rien n'est modifié.

    python manage.py comparer_fiche_rh PR00123
"""
from django.core.management.base import BaseCommand, CommandError

from utilisateurs.models import Employe
from utilisateurs.services_rh import ApiRhIndisponible, _postes_depuis, lire_employes_externes


class Command(BaseCommand):
    help = "Compare une fiche Ikarama avec l'API RH (lecture seule)."

    def add_arguments(self, parser):
        parser.add_argument('matricule')

    def handle(self, matricule, **options):
        code = matricule.strip().upper()
        try:
            donnees = lire_employes_externes(utiliser_cache=False)   # toujours la version la plus récente
        except ApiRhIndisponible as exc:
            raise CommandError(str(exc))

        rh = next((e for e in donnees if str(e.get('codeBarre', '')).strip().upper() == code), None)
        if rh is None:
            raise CommandError(f"{code} est absent de l'API RH ({len(donnees)} employés renvoyés).")

        def postes_rh():
            return [((p.get('poste') or {}).get('nom'), (p.get('poste') or {}).get('statut'), p.get('pole'))
                    for p in _postes_depuis(rh)]

        employe = Employe.objects.filter(code_barre__iexact=code).first()
        ikarama = list(employe.postes.values_list('poste_nom', 'poste_statut', 'pole')) if employe else None

        self.stdout.write(f"\n{code}")
        self.stdout.write(f"  Prénom usuel  API RH : {rh.get('prenomUsuel')!r:30}  Ikarama : "
                          f"{(employe.prenom_usuel if employe else None)!r}")
        self.stdout.write(f"  Postes        API RH : {postes_rh()}")
        self.stdout.write(f"                Ikarama: {ikarama}")
        identiques = ikarama is not None and sorted(map(str, postes_rh())) == sorted(map(str, ikarama))
        self.stdout.write(self.style.SUCCESS("  -> postes identiques") if identiques
                          else self.style.WARNING("  -> postes différents : la prochaine ouverture les mettra à jour"))
