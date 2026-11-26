# backend/ikarama/accueil.py
"""
Page d'accueil (première page après la connexion), selon le profil :
  employé       : ma semaine (heures par jour, erreurs), mes lignes en orange / rouge, mes notes moyennes ;
  mon équipe    : pointages incomplets de la semaine en cours, pour les personnes du périmètre « Voir » de
                  Pointages > Vérification (seulement par un rôle) ;
  responsable   : lignes de mes affaires en orange / rouge, avancement de mes feuilles ;
  administrateur: nombre de problèmes des Contrôles de cohérence, activité récente des feuilles.
  GET /api/accueil/
"""
from ikarama.temps import aujourdhui
from collections import defaultdict
from datetime import date as Date
from datetime import timedelta

from django.db.models import Avg, Q, Sum
from rest_framework.response import Response
from rest_framework.views import APIView

from autorisations.acces import q_acces
from autorisations.permissions import est_administrateur
from utilisateurs.serializers import EmployeResumeSerializer


def _lignes_en_alerte(lignes, limite=12):
    from gsheets.services import alerte_ligne
    resultat = []
    for l in lignes.filter(temps_prod__gt=0).select_related(
            'feuille', 'employe', 'statut', 'description__projet__affaire', 'description__projet__rendement'):
        alerte = alerte_ligne(l)
        if alerte:
            resultat.append({
                'alerte': alerte, 'feuille': l.feuille.nom, 'feuille_id': l.feuille_id, 'numero': l.numero,
                'description': l.description.nom, 'affaire': l.description.projet.affaire.nom,
                'employe': l.employe.identifiant if l.employe else None, 'temps_prod': float(l.temps_prod),
            })
    resultat.sort(key=lambda x: (x['alerte'] != 'rouge', -x['temps_prod']))
    return {'nombre': len(resultat), 'rouges': sum(1 for x in resultat if x['alerte'] == 'rouge'), 'lignes': resultat[:limite]}


class AccueilView(APIView):
    def get(self, request):
        from gsheets.models import Feuille, HistoriqueLigne, LigneFeuille
        from marches.models import Affaire
        from pointages.calculs import est_ouvrable
        from pointages.erreurs import erreurs_pointage
        from pointages.models import Pointage

        moi = getattr(request.user, 'employe', None)
        aujourd_hui = aujourdhui()
        lundi = aujourd_hui - timedelta(days=aujourd_hui.weekday())
        reponse = {'employe': EmployeResumeSerializer(moi).data if moi else None, 'date': aujourd_hui.isoformat()}

        # --- Employé ---------------------------------------------------------------
        if moi:
            pointages = Pointage.objects.filter(employe=moi, date__gte=lundi, date__lte=aujourd_hui)
            par_jour = {p['date']: (p['n'] or 0) + (p['h'] or 0)
                        for p in pointages.values('date').annotate(n=Sum('minutes_normales'), h=Sum('minutes_hs'))}
            semaine = [{'date': (lundi + timedelta(days=i)).isoformat(), 'minutes': par_jour.get(lundi + timedelta(days=i), 0),
                        'ouvrable': i < 5, 'futur': lundi + timedelta(days=i) > aujourd_hui} for i in range(7)]
            # Mon planning : les 7 prochains jours (projets planifiés pour moi)
            from planning.models import AffectationPlanning
            planning = defaultdict(list)
            for a in (AffectationPlanning.objects.filter(employe=moi, date__gte=aujourd_hui, date__lte=aujourd_hui + timedelta(days=6))
                      .select_related('projet__affaire', 'projet__prestation')):
                planning[a.date.isoformat()].append({'projet': a.projet.nom, 'affaire': a.projet.affaire.nom,
                                                     'prestation': a.projet.prestation.nom})
            reponse['moi'] = {
                'planning': [{'date': (aujourd_hui + timedelta(days=i)).isoformat(), 'ouvrable': est_ouvrable(aujourd_hui + timedelta(days=i)),
                              'projets': planning.get((aujourd_hui + timedelta(days=i)).isoformat(), [])} for i in range(7)],
                'semaine': semaine,
                'minutes_aujourdhui': par_jour.get(aujourd_hui, 0),
                'minutes_semaine': sum(par_jour.values()),
                'erreurs': erreurs_pointage(moi, lundi, aujourd_hui),
                'alertes': _lignes_en_alerte(LigneFeuille.objects.filter(employe=moi, description__isnull=False)),
            }

        # --- Mon équipe : pointages incomplets de la semaine en cours ------------------------
        #     Seulement avec le droit « Voir » de Pointages > Vérification (par un rôle), sur son périmètre.
        from autorisations.droits import peut, q_droit
        if moi and peut(request.user, 'pointages_verification', 'voir'):
            from utilisateurs.models import Employe
            equipe = (Employe.objects.filter(q_acces()).filter(q_droit(request.user, 'pointages_verification', 'voir'))
                      .exclude(pk=moi.pk).distinct().order_by('nom', 'prenom'))
            dimanche = lundi + timedelta(days=6)
            manques = []
            for personne in equipe:
                # Jours ouvrables de la semaine jusqu'à aujourd'hui compris (même règle que Mon temps)
                erreurs = [e for e in erreurs_pointage(personne, lundi, dimanche) if e['type'] == 'INCOMPLET']
                if erreurs:
                    manques.append({'employe': EmployeResumeSerializer(personne).data, 'jours': len(erreurs),
                                    'manque_minutes': sum(8 * 60 - e['minutes'] for e in erreurs),
                                    'detail': [e['message'] for e in erreurs]})
            manques.sort(key=lambda m: -m['manque_minutes'])
            reponse['equipe'] = {
                'nb_equipe': equipe.count(),
                'periode': {'debut': lundi.isoformat(), 'fin': dimanche.isoformat()},
                'manques': manques[:50], 'nb_manques': len(manques),
            }

        # --- Responsable : mes affaires (lignes à surveiller, avancement des feuilles) ---------
        affaires = Affaire.objects.filter(actif=True, responsables=moi) if moi else Affaire.objects.none()
        if moi and affaires.exists():
            feuilles = (Feuille.objects.filter(perimetres__affaire__in=affaires).distinct()
                        .annotate(avancement=Avg('lignes__avancement')).order_by('nom'))
            reponse['responsable'] = {
                'nb_affaires': affaires.count(),
                'alertes': _lignes_en_alerte(LigneFeuille.objects.filter(description__projet__affaire__in=affaires)),
                'feuilles': [{'id': f.id, 'nom': f.nom, 'avancement': round(f.avancement or 0),
                              'nb_lignes': f.lignes.filter(description__isnull=False).count()} for f in feuilles[:10]],
            }

        # --- Administrateur ----------------------------------------------------------------
        from autorisations.droits import peut as peut_droit
        if peut_droit(request.user, 'parametres_controles', 'voir'):
            from .controles import controles
            liste = controles()
            activite = (HistoriqueLigne.objects.select_related('auteur', 'feuille', 'ligne').order_by('-date')[:8]
                        if est_administrateur(request.user) else [])
            reponse['administrateur'] = {
                'controles': [{'code': c['code'], 'titre': c['titre'], 'gravite': c['gravite'], 'nombre': c['nombre']}
                              for c in liste if c['nombre']],
                'total_controles': sum(c['nombre'] for c in liste),
                'activite': [{'date': h.date.isoformat(), 'auteur': h.auteur.identifiant if h.auteur else '—',
                              'feuille': h.feuille.nom, 'feuille_id': h.feuille_id,
                              'ligne': h.ligne.numero if h.ligne else None, 'libelle': h.libelle,
                              'nouvelle_valeur': (h.nouvelle_valeur or '')[:80]} for h in activite],
            }
        return Response(reponse)
