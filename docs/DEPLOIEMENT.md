# Mise en production (Linux, nginx)

Ce guide décrit une installation sur un serveur Linux (Debian / Ubuntu) avec nginx devant l'application.
Adapter les chemins, l'utilisateur système et les noms de domaine à votre serveur.

```
Navigateur ──HTTPS──> nginx ──┬── /            fichiers du frontend (frontend/build)
                              ├── /api/  /admin/ /static/  ──> Daphne (127.0.0.1:4000)
                              └── /ws/   (WebSocket)        ──> Daphne (127.0.0.1:4000)
                                         Daphne ──> PostgreSQL, Redis (facultatif)
```

## 1. Prérequis

- Python 3.10+, Node.js 20+ (seulement pour construire le frontend), PostgreSQL, nginx.
- **Redis** (facultatif) : `sudo apt install redis-server`. Obligatoire dès qu'on lance **plusieurs processus** serveur.
- Un certificat HTTPS (le WebSocket passe alors en `wss://`).

## 2. Installation

```bash
sudo mkdir -p /opt/ikarama && sudo chown $USER /opt/ikarama
git clone <dépôt> /opt/ikarama && cd /opt/ikarama
cp .env.example .env && nano .env        # voir la section 3

cd backend
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser          # compte de secours (/admin/)

cd ../frontend
npm ci && npm run build                   # produit frontend/build
```

## 3. Réglages de production (`.env`)

| Variable | Valeur conseillée |
|---|---|
| `DEBUG` | `False` |
| `SECRET_KEY` | une valeur longue et propre à ce serveur |
| `ALLOWED_HOSTS` | `ikarama.exemple.mg` (le nom du site) |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | `https://ikarama.exemple.mg` |
| `HTTPS` | `True` |
| `CA_BUNDLE` | `systeme` ou le chemin d'un `.pem` (recommandé). `desactive` est accepté (aucune vérification des certificats de Keycloak et de l'API RH) : c'est alors à l'équipe de déploiement de gérer ce risque ; un avertissement s'affiche au démarrage et dans Paramètres > Contrôles de cohérence |
| `VITE_BACKEND_URL` | `https://ikarama.exemple.mg` (même adresse : nginx répartit) |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` si Redis est installé, sinon vide |
| `VITE_WS_URL` | vide (déduit de `VITE_BACKEND_URL`), ou `wss://…` si le WebSocket a une autre adresse |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL`, `URL_APPLICATION` | serveur d'envoi et adresse du site |

Les variables `VITE_*` sont lues **au moment du `npm run build`** : reconstruire le frontend après les avoir changées.

## 4. Service du serveur (systemd)

`/etc/systemd/system/ikarama.service` :

```ini
[Unit]
Description=Ikarama (Daphne : HTTP et WebSocket)
After=network.target postgresql.service redis-server.service

[Service]
User=ikarama
WorkingDirectory=/opt/ikarama/backend
ExecStart=/opt/ikarama/backend/venv/bin/daphne -b 127.0.0.1 -p 4000 ikarama.asgi:application
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ikarama
sudo systemctl status ikarama
```

**Un seul processus Daphne** suffit pour quelques dizaines d'utilisateurs, et fonctionne sans Redis.
Pour plusieurs processus (par exemple `uvicorn ikarama.asgi:application --workers 4`), **Redis est obligatoire**.

## 5. nginx

`/etc/nginx/sites-available/ikarama` :

```nginx
map $http_upgrade $connection_upgrade { default upgrade; '' close; }

server {
    listen 443 ssl;
    server_name ikarama.exemple.mg;
    ssl_certificate     /etc/ssl/ikarama/fullchain.pem;
    ssl_certificate_key /etc/ssl/ikarama/privkey.pem;
    client_max_body_size 10m;                 # imports Excel (5 Mo maximum côté application)

    root /opt/ikarama/frontend/build;
    location / { try_files $uri $uri/ /index.html; }

    location ~ ^/(api|admin|static)/ {
        proxy_pass http://127.0.0.1:4000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 180s;               # imports volumineux
    }

    # WebSocket (temps réel)
    location /ws/ {
        proxy_pass http://127.0.0.1:4000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;              # connexion longue
    }
}
server { listen 80; server_name ikarama.exemple.mg; return 301 https://$host$request_uri; }
```

```bash
sudo ln -s /etc/nginx/sites-available/ikarama /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

**Vérifier le temps réel** : ouvrir une feuille ; l'icône éclair à côté de « En direct » doit apparaître.
Sans elle, l'application fonctionne quand même (interrogation toutes les 4 s) : vérifier le bloc `location /ws/`.

## 6. Tâches planifiées (crontab)

`crontab -e` avec l'utilisateur du service :

```cron
0 8 * * 1-5  cd /opt/ikarama/backend && venv/bin/python manage.py envoyer_rappels --veille     >> /var/log/ikarama/rappels.log 2>&1
0 15 * * 5   cd /opt/ikarama/backend && venv/bin/python manage.py envoyer_rappels --semaine    >> /var/log/ikarama/rappels.log 2>&1
0 17 * * *   cd /opt/ikarama/backend && venv/bin/python manage.py envoyer_recapitulatif        >> /var/log/ikarama/emails.log 2>&1
30 1 * * *   pg_dump -Fc ikarama > /sauvegardes/ikarama-$(date +\%F).dump
```

Essayer d'abord chaque commande avec `--simulation`.

## 7. Mettre à jour

```bash
cd /opt/ikarama && git pull
cd backend && . venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py test                     # facultatif, sur une copie de la base
cd ../frontend && npm ci && npm run build
sudo systemctl restart ikarama
```

Branches : `develop` déploie le serveur de test, `main` la production.

## 8. Sauvegarde et restauration

- Base : `pg_dump -Fc ikarama > ikarama.dump` ; restauration : `pg_restore -c -d ikarama ikarama.dump`.
- Conserver aussi le fichier `.env` (en lieu sûr : il contient les secrets).
- Tester une restauration de temps en temps, sur un autre serveur.
