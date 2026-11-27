# Ikarama — suivi des pointages

Application de suivi des pointages et du rendement, construite sur le socle d'Alimanaka (authentification, utilisateurs, équipes).

| Partie | Technologies |
| --- | --- |
| Backend | Python 3.10+, Django 5.2, Django REST Framework, Django Channels (WebSocket), PostgreSQL |
| Frontend | Node.js 20+, Vue 3, TypeScript, Vite, Pinia, Vue Router |
| Identité | Keycloak (SSO) ; chaque jeton est validé par Keycloak |
| Temps réel | WebSocket `/ws/` (Daphne) ; Redis facultatif |

Un seul fichier `.env`, à la racine, sert au backend **et** au frontend. Modèle commenté : `.env.example`.

**Documentation**

- `docs/guide/` : **guide utilisateur** (employé, responsable, administrateur), aussi affiché dans l'application (menu **Aide**) ;
- `docs/DEPLOIEMENT.md` : **mise en production** sur Linux avec nginx (WebSocket, Redis, tâches planifiées, mise à jour) ;
- `docs/CI-CD.md` : **CI/CD GitHub Actions** (vérifier, installer, tester à chaque push ; déployer `main` dans la
  VirtualBox par un runner auto-hébergé : `.github/workflows/ci-cd.yml`, `deploiement/`) ;
- ce fichier : démarrage, organisation du code, recettes.

---

## 1. Démarrer en local

```bash
cp .env.example .env            # puis renseigner les valeurs (secrets : jamais dans Git)

# Backend
cd backend
python -m venv venv
venv\Scripts\activate           # Windows   (Linux/macOS : source venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py test           # environ 200 tests doivent passer
python manage.py runserver 0.0.0.0:4000   # serveur ASGI (Daphne) : HTTP et WebSocket

# Frontend (second terminal)
cd frontend
npm install
npm run dev                     # http://<adresse du poste>:4002
```

- Essai rapide sans PostgreSQL : `DB_ENGINE=sqlite` dans `.env`.
- Sans `REDIS_URL`, le temps réel fonctionne en mode mémoire (un seul processus serveur : c'est le cas de `runserver`).
- Sans `EMAIL_HOST`, les e-mails s'affichent dans la console du serveur.

**Keycloak** : dans le client utilisé par le frontend, déclarer *Valid redirect URIs*, *Web origins* et *Valid post logout redirect URIs* pour `http://localhost:4002/` et l'adresse de chaque serveur.

### Réglages principaux (`.env`)

| Variable | Rôle |
| --- | --- |
| `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `HTTPS` | Sécurité Django |
| `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Base de données |
| `CA_BUNDLE` | Certificats pour Keycloak et l'API RH : `systeme` ou chemin d'un `.pem` (recommandé) ; `desactive` = aucune vérification (accepté même avec `DEBUG=False`, signalé au démarrage et dans les Contrôles de cohérence) |
| `KEYCLOAK_*`, `VITE_KEYCLOAK_*` | Connexion (SSO) |
| `EXTERNAL_API_*`, `SYNC_CONNEXION_INTERVALLE_HEURES` | API RH (fiches employés, synchronisation à la connexion) |
| `VITE_BACKEND_URL`, `VITE_FRONTEND_PORT`, `VITE_PHOTO_PROFIL_URL` | Frontend |
| `REDIS_URL`, `VITE_WS_URL` | Temps réel (voir plus bas) |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL`, `URL_APPLICATION` | E-mail récapitulatif des notifications |

---

## 2. Organisation du code

### Backend (`backend/`)

| Dossier | Rôle |
| --- | --- |
| `ikarama/` | Configuration (`settings.py`, `asgi.py`), URL et briques communes : `vues.py` (filtres, ordre manuel, export Excel `ExportExcelMixin`, `reponse_excel`), `importation.py` (import Excel `ImportExcelMixin` : modèle, aperçu, avertissements, regroupement), `accueil.py` (page d'accueil par profil), `controles.py` (Contrôles de cohérence), `gestion_erreurs.py` |
| `authentification/` | Validation des jetons Keycloak et rattachement à la fiche employé. `GET /api/auth/moi/` |
| `autorisations/` | **Point d'entrée unique des droits** : `permissions.py` (contrôle de chaque requête), `acces.py` (Accès au site), `droits.py` (**moteur de Paramètres > Autorisation** : droits de base, rôles Autoriser / Refuser, périmètres ; `peut`, `q_droit`, `peut_sur`, `verifier`, `expliquer`), `vues_roles.py` (API des rôles) |
| `utilisateurs/` | Employés et postes, synchronisation API RH (`services_rh.py`) |
| `equipes/` | Équipes **calculées** depuis les fiches (N+1 et collaborateurs directs, pôles, organigramme) |
| `marches/` | Marché : prestations et rendements objectifs, tâches (type, plusieurs descriptions, temps du projet), statuts (couleur et rôles), chaîne Affaire > Prestations > Projets / Communes > Descriptions ; Temps et Statut calculés depuis les feuilles (`suivi.py`) ; Durée estimatif par projet (`duree.py`) ; Configurations Responsables (`configurations.py`) |
| `gsheets/` | Feuilles : une ligne par description, tenue à jour avec le Marché (`services.py`, `signals.py`) ; saisie avec conflits case par case, historique, présence (`presence.py`) ; Temps Estimatif et alertes ; imports (données, feuilles, anciennes données `import_ancien.py`) ; résumé du profil |
| `pointages/` | Mon temps (`PartPointage` : une ou plusieurs descriptions), H_Durée / HS / pause (`calculs.py`), report et verrou dans les feuilles (`services.py`), erreurs (`erreurs.py`), Suivi et Vérification (`suivi.py`), Affichage Everwin (`everwin.py`) |
| `rendements/` | Paramètres Rendement & Note et formules des feuilles (`calculs.py`) ; onglets du Rendement (`analyse.py` : Globale, Evolution, Analyse, Réel vs Objectif, Evaluation) avec une source de temps commune (pointages ou données des feuilles) ; Paramètres > Graphiques |
| `planning/` | Planning Projet : affectations planifiées (projet / commune, personne, jour), grille de la semaine (pointages, planifié, « en train de faire »), réglage du statut |
| `notifications/` | Notifications (cloche), déclencheurs, commandes `envoyer_rappels` et `envoyer_recapitulatif` |
| `temps_reel/` | WebSocket `/ws/` (`consumers.py`) et diffusion des changements (`diffusion.py`, `signaux.py`) |
| `affichage_ev/`, `profils/` | Réservés |

Date et heure du jour côté serveur : toujours `ikarama.temps.aujourdhui()` / `maintenant()` (fuseau `TIME_ZONE` du `.env`).

Format d'erreur de toute l'API : `{"detail": "message lisible", "erreurs": {"champ": ["..."]}}`.

### Frontend (`frontend/src/`)

| Dossier | Rôle |
| --- | --- |
| `api/client.ts` | **Client HTTP unique** : jeton, renouvellement après 401, erreurs lisibles (`ApiErreur`) |
| `api/ressource.ts`, `api/*.ts` | Fabrique `creerRessource('/chemin/')` ; un fichier par domaine, importé via `@/api` |
| `services/session.ts` | Connexion Keycloak (PKCE) |
| `config/navigation.ts`, `router/index.ts` | Menu latéral et routes |
| `store/` | `auth`, `interface`, `selectionRendement` (synchronisation et source des données du Rendement) |
| `composables/` | `useListe`, `useRequete`, `useToast`, `useConfirmation`, `useSuiviFeuille`, **`useTempsReel`** (connexion WebSocket unique, reconnexion, repli ; feuilles, présences, notifications, planning), `useSynchronisationRendement`, `useSourceDonnees` |
| `components/ui/` | Briques d'interface ; `TableauDonnees.vue` (tableau standard), `ImportExcel.vue` (import commun) |
| `components/rendement/` | Graphiques en SVG (barres, courbes, bulles, camembert, jauge) et listes de filtres |
| `components/notifications/Cloche.vue` | Cloche de l'en-tête |
| `views/` | Une page par écran (`accueil/`, `pointages/`, `feuilles/`, `marches/`, `rendement/`, `planning/`, `parametres/`, `aide/`…) |
| `components/planning/`, `components/autorisations/` | Filtre à choix multiples du Planning ; listes de périmètres et choix avec recherche de Paramètres > Autorisation |
| `style.css` | Feuille de style globale (`--marine` #18355D, `--rouge` #E94242) |

---

## 3. Temps réel

- Chaque onglet ouvre **une** connexion WebSocket (`/ws/`), authentifiée par le jeton Keycloak dans le premier message.
- Le serveur signale « la feuille 3 a changé », « nouvelle présence », « nouvelle notification », « le planning a changé »
  (planification, pointage, statut d'une ligne) ; la page relit ce qui a changé par l'API, avec ses propres droits.
- Icône de l'onglet du navigateur : `frontend/public/favicon_3.svg`, déclarée dans `frontend/index.html` (`<link rel="icon">`).
- Si le WebSocket ne passe pas, la page **se rabat** sur l'interrogation régulière (toutes les 4 s pour une feuille,
  toutes les 30 s pour le Planning, chaque minute pour la cloche). L’icône éclair à côté de « En direct » indique que le temps réel est actif.
- **Un seul processus serveur** : `REDIS_URL` peut rester vide. **Plusieurs processus** (ou plusieurs serveurs) : `REDIS_URL` est obligatoire, sinon les événements et les présences ne passent pas d'un processus à l'autre.

## 4. Tâches planifiées

| Commande | Quand | Rôle |
|---|---|---|
| `python manage.py envoyer_rappels --veille` | jours ouvrables, 8h00 | rappel du pointage incomplet de la veille |
| `python manage.py envoyer_rappels --semaine` | vendredi, 15h00 | rappel de la semaine incomplète |
| `python manage.py envoyer_recapitulatif` | tous les jours, 17h00 | un e-mail par personne avec ses notifications non lues |

Chaque commande accepte `--simulation`. Exemples de crontab dans `docs/DEPLOIEMENT.md`.

## 5. Accès au site (Paramètres > Accès au site)

- Règles **Autoriser** / **Refuser** par pôle, poste, matricule ou responsable N+1. Un refus l'emporte toujours ; sans règle « Autoriser », le site est ouvert à tous.
- Contrôlé côté serveur à chaque requête (WebSocket compris), **superadmins compris**.
- **Secours** : `/admin/` avec un compte `createsuperuser`, ou `python manage.py acces_site` (`--verifier`, `--autoriser`, `--tout-desactiver`).

## 6. Autorisation (Paramètres > Autorisation)

- **Décision** = droits de base + rôles « Autoriser » − rôles « Refuser » (un refus l'emporte toujours). Superadmin : tout.
- Modules gérés (`droits.MODULES`) : `pointages_suivi`, `pointages_verification`, `gsheets_feuilles`, `marches_affaires`,
  `marches_prestations`, `marches_projets`, `marches_descriptions`, `marches_taches`, `marches_statuts`, `marches_archives`,
  `marches_duree`.
  Postes et pôles comparés de façon tolérante (`autorisations/intitules.py`) ; diagnostic dans
  `autorisations/verification.py` (Paramètres > Vérification des droits) ; droits relus en temps réel (événement `droits`).
  Modules `affichage_everwin` et `planning_projet` : par défaut, les siens seulement. `parametres_controles` : la page
  des Contrôles de cohérence par un rôle (le reste de Paramètres reste au superadmin). Autre droit de base : voir les feuilles de ses affaires. Plusieurs périmètres par action ; périmètre « Équipe de ».
- Côté serveur : `module = '...'` sur la vue (contrôle « au moins une partie »), puis `q_droit(...)` pour filtrer les listes
  et `verifier(..., objet)` pour un objet précis. Côté écran : `auth.peut('creer', 'gsheets_feuilles')`.
- Ajouter un module : une entrée dans `MODULES` (et ses droits de base dans `BASE`), puis brancher la vue.

## 7. Recettes

**Ajouter un écran de gestion** : un modèle, un serializer, un viewset avec `module = '...'`, une ligne dans `urls.py` ; côté frontend `creerRessource`, puis `GestionCrud` ou `TableauDonnees`.

**Ajouter une page au menu** : une entrée dans `config/navigation.ts` et une route dans `router/index.ts`.

**Ajouter un import Excel** : `ImportExcelMixin` sur le viewset (`import_colonnes`, `importer_ligne`), puis `ImportExcel.vue` côté frontend.

**Diffuser un changement en temps réel** : `temps_reel.diffusion.diffuser(groupe, {...})` (envoyé après la validation de la transaction) ; côté frontend `useTempsReel().ecouter(type, fonction)`.

## 8. Points d'attention

- **Avant la production** : `DEBUG=False`, une `SECRET_KEY` propre à la production, des mots de passe changés et jamais
  transmis en clair. `CA_BUNDLE=systeme` (ou un `.pem`) est recommandé ; avec `CA_BUNDLE=desactive`, la vérification des
  certificats de Keycloak et de l'API RH est coupée (à la charge de l'équipe de déploiement).
- Sauvegarder la base PostgreSQL chaque jour et tester une restauration.
- Les jours fériés et les congés ne sont pas encore connus : un jour férié non pointé apparaît en erreur et déclenche un rappel.
- Les signaux de l'onglet Analyse aident à poser une question : ils ne remplacent pas un échange avec la personne.
- Relire et tester tout contenu avant mise en production.
