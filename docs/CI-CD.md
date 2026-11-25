# CI/CD avec GitHub Actions et une VirtualBox

À chaque `git push` (toutes les branches) et à chaque pull request, GitHub **vérifie, installe et teste** Ikarama.
Pour un push sur **`main`**, si tout est vert, Ikarama est **déployé dans la VirtualBox** :
`/home/user/projets/ikarama_v2` est mis à jour (ou créé s'il n'existe pas).

| Étape | Où | Contenu |
|---|---|---|
| Backend | machines GitHub | `pip install`, `check`, migrations manquantes, tests (SQLite, sans secret) |
| Frontend | machines GitHub | `npm ci`, vérification des types, compilation |
| Déploiement (`main`) | **la VM** (runner auto-hébergé) | `deploiement/deployer.sh` |

**Pourquoi un runner dans la VM ?** GitHub ne peut pas joindre une machine de ton réseau local. Le runner, installé
dans la VM, va lui-même chercher le travail chez GitHub (connexion **sortante** seulement) : aucun port à ouvrir,
aucun mot de passe SSH stocké chez GitHub.

**Ce que le déploiement ne touche jamais** : le dossier `Absences`, le fichier `.env` de la VM (il ne passe jamais
par GitHub), `backend/venv`, `backend/media`, `backend/logs`, la base de données (sauvegardée puis seulement migrée).

---

## 1. Préparer la VM (une fois)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip rsync curl git nginx postgresql postgresql-client
# Node.js 20 ou plus récent (si `node --version` est trop ancien) :
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt install -y nodejs
```

## 2. Dépôt GitHub

- Le dépôt doit être **privé** : un runner auto-hébergé sur un dépôt public pourrait exécuter le code de n'importe qui.
- Pousser le projet : `git push origin main` (le dossier `.github/workflows/` est inclus).
- Facultatif, dans **Settings > Secrets and variables > Actions > Variables** :
  `IKARAMA_DOSSIER` (défaut `/home/user/projets/ikarama_v2`), `IKARAMA_SERVICE` (défaut `ikarama`),
  `IKARAMA_URL_SANTE` (défaut `http://127.0.0.1:4000/admin/login/`).
- Facultatif : **Settings > Environments > production** pour exiger une validation avant chaque déploiement.

## 3. Installer le runner dans la VM (une fois)

1. Sur GitHub : **Settings > Actions > Runners > New self-hosted runner**, choisir **Linux** et **x64**.
2. Dans la VM, avec ton utilisateur (`user`, pas `root`), suivre les commandes affichées par GitHub
   (téléchargement dans `~/actions-runner`, puis `./config.sh --url … --token …`).
   Quand `config.sh` demande des **étiquettes** (labels), répondre : `ikarama`
3. L'installer comme service, pour qu'il tourne en permanence et au redémarrage de la VM :
   ```bash
   cd ~/actions-runner
   sudo ./svc.sh install user
   sudo ./svc.sh start
   ```
4. Sur GitHub, le runner apparaît **Idle** (vert) dans Settings > Actions > Runners.

## 4. Premier déploiement et fichier `.env`

1. Faire un push sur `main` (ou **Actions > CI/CD Ikarama > Run workflow**).
2. Le premier déploiement **crée** `/home/user/projets/ikarama_v2` (ou le met à jour ; s'il contenait déjà des
   fichiers, une copie de sécurité `ikarama_v2_avant_ci_<date>` est faite), y copie le code, puis **s'arrête** :
   un modèle `.env` a été posé.
3. Compléter `/home/user/projets/ikarama_v2/.env` (base de données, Keycloak, `SECRET_KEY`, `ALLOWED_HOSTS`…).
   Pour la VM, avec nginx sur le port 4002 (étape 7) :
   ```
   DEBUG=False
   ALLOWED_HOSTS=<IP_DE_LA_VM>,localhost,127.0.0.1
   CORS_ALLOWED_ORIGINS=http://<IP_DE_LA_VM>:4002
   CSRF_TRUSTED_ORIGINS=http://<IP_DE_LA_VM>:4002
   VITE_BACKEND_URL=http://<IP_DE_LA_VM>:4002
   ```
   (`hostname -I` donne l'adresse IP de la VM.) Dans Keycloak, ajouter `http://<IP_DE_LA_VM>:4002/` aux
   *Valid redirect URIs*, *Web origins* et *Valid post logout redirect URIs* du client.
4. Base PostgreSQL : la créer, ou y restaurer ta base actuelle (`pg_restore`, voir la réponse sur le transfert).
5. Relancer le déploiement : **Actions > le dernier passage > Re-run jobs**.

## 5. Service systemd (une fois)

```bash
cd /home/user/projets/ikarama_v2
sudo cp deploiement/ikarama.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ikarama
systemctl status ikarama
```

## 6. Autoriser le runner à redémarrer Ikarama (une fois)

Le déploiement redémarre le service avec `sudo`, sans mot de passe, et **seulement** pour cette commande :

```bash
echo 'user ALL=(root) NOPASSWD: /usr/bin/systemctl restart ikarama, /bin/systemctl restart ikarama' | sudo tee /etc/sudoers.d/ikarama-deploiement
sudo chmod 440 /etc/sudoers.d/ikarama-deploiement
sudo visudo -c
```

## 7. nginx (une fois)

```bash
cd /home/user/projets/ikarama_v2
sudo cp deploiement/nginx-ikarama.conf /etc/nginx/sites-available/ikarama
sudo ln -s /etc/nginx/sites-available/ikarama /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
# nginx (utilisateur www-data) doit pouvoir lire le frontend compilé :
chmod o+x /home/user /home/user/projets /home/user/projets/ikarama_v2 /home/user/projets/ikarama_v2/frontend
```

Ikarama est alors sur **http://<IP_DE_LA_VM>:4002**.

## Ensuite : à chaque push sur `main`

`deploiement/deployer.sh`, lancé dans la VM :

1. met à jour le code (`rsync`) sans toucher au `.env`, au `venv`, à `media/`, à `logs/` ;
2. installe les dépendances Python ;
3. **sauvegarde la base** (`pg_dump`, ou copie SQLite) dans `/home/user/projets/sauvegardes/ikarama/`
   (les 10 dernières sont gardées) ; si la sauvegarde échoue, le déploiement s'arrête **avant** les migrations ;
4. `check`, `migrate`, `collectstatic` ;
5. compile le frontend (avec les `VITE_*` du `.env` de la VM) ;
6. redémarre le service et vérifie qu'Ikarama répond.

## Dépannage

| Message | Cause |
|---|---|
| Le job « Déployer » reste « Waiting for a runner » | Le runner est arrêté : `sudo ~/actions-runner/svc.sh status` ou `start` |
| « aucun .env » | Premier déploiement : compléter le `.env` puis Re-run |
| « sauvegarde PostgreSQL impossible » | Vérifier `DB_USER`, `DB_PASSWORD`, `DB_NAME` dans le `.env` |
| « redémarrage refusé » | La règle sudo de l'étape 6 manque |
| « Ikarama ne répond pas correctement » | `journalctl -u ikarama -n 50` |
| Page blanche dans le navigateur | Droits de lecture de nginx (fin de l'étape 7) ou `VITE_BACKEND_URL` |

**Revenir en arrière** : faire un `git revert` du commit fautif et le pousser sur `main` (le déploiement repasse) ;
en cas de problème de base, restaurer la sauvegarde faite juste avant (`pg_restore -c -d <base> <fichier>.dump`).
