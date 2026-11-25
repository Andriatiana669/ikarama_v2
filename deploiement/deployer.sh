#!/usr/bin/env bash
# deploiement/deployer.sh — met à jour (ou crée) l'installation d'Ikarama dans la VM.
# Lancé par le runner GitHub auto-hébergé (voir .github/workflows/ci-cd.yml et docs/CI-CD.md),
# ou à la main :  bash deploiement/deployer.sh <dossier du code>
#
# Réglages (variables d'environnement) :
#   IKARAMA_DOSSIER     dossier de l'installation      (défaut : /home/user/projets/ikarama_v2)
#   IKARAMA_SERVICE     service systemd à redémarrer  (défaut : ikarama ; vide = pas de redémarrage)
#   IKARAMA_URL_SANTE   adresse vérifiée à la fin      (défaut : http://127.0.0.1:4000/admin/login/)
#   IKARAMA_SAUVEGARDES dossier des sauvegardes        (défaut : <dossier>/../sauvegardes/ikarama)
#
# Ce qui n'est JAMAIS écrasé ni supprimé : .env, backend/venv, frontend/node_modules, backend/media,
# backend/logs, backend/staticfiles, la base de données (seulement sauvegardée puis migrée).
set -euo pipefail

SOURCE="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
DOSSIER="${IKARAMA_DOSSIER:-/home/user/projets/ikarama_v2}"
SERVICE="${IKARAMA_SERVICE-ikarama}"
URL_SANTE="${IKARAMA_URL_SANTE:-http://127.0.0.1:4000/admin/login/}"
SAUVEGARDES="${IKARAMA_SAUVEGARDES:-$(dirname "$DOSSIER")/sauvegardes/ikarama}"
HORODATAGE="$(date +%Y%m%d-%H%M%S)"
MARQUEUR="$DOSSIER/.deploiement-ikarama"

etape() { echo; echo "==> $*"; }
echec() { echo "ERREUR : $*" >&2; exit 1; }

[ -d "$SOURCE/backend" ] && [ -d "$SOURCE/frontend" ] || echec "code introuvable dans $SOURCE"
case "$DOSSIER" in /|/home|/home/*/|"") echec "dossier d'installation refusé : « $DOSSIER »";; esac
for outil in rsync python3 npm; do command -v "$outil" >/dev/null || echec "« $outil » n'est pas installé dans la VM"; done

# --------------------------------------------------------------------------------------------
etape "1. Dossier d'installation : $DOSSIER"
if [ ! -d "$DOSSIER" ]; then
  echo "Il n'existe pas : création."
  mkdir -p "$DOSSIER"
elif [ ! -f "$MARQUEUR" ] && [ -n "$(ls -A "$DOSSIER" 2>/dev/null)" ]; then
  # Premier déploiement automatique dans un dossier déjà rempli à la main : on en garde une copie
  COPIE="${DOSSIER}_avant_ci_${HORODATAGE}"
  echo "Dossier existant, jamais déployé par la CI : copie de sécurité dans $COPIE"
  cp -a "$DOSSIER" "$COPIE"
fi

# --------------------------------------------------------------------------------------------
etape "2. Mise à jour du code (rsync)"
rsync -a --delete \
  --exclude '.git/' --exclude '.github/' \
  --exclude '.env' --exclude '.deploiement-ikarama' \
  --exclude 'backend/venv/' --exclude 'backend/.venv/' --exclude 'backend/staticfiles/' \
  --exclude 'backend/media/' --exclude 'backend/logs/' --exclude 'backend/db.sqlite3' \
  --exclude 'frontend/node_modules/' --exclude 'frontend/build/' \
  --exclude '__pycache__/' --exclude '*.pyc' \
  "$SOURCE/" "$DOSSIER/"

# --------------------------------------------------------------------------------------------
etape "3. Fichier .env"
if [ ! -f "$DOSSIER/.env" ]; then
  cp "$DOSSIER/.env.example" "$DOSSIER/.env"
  chmod 600 "$DOSSIER/.env"
  echec "aucun .env : un modèle a été copié dans $DOSSIER/.env. Complétez-le (base, Keycloak, SECRET_KEY…), puis relancez le déploiement (onglet Actions > Re-run jobs)."
fi
chmod 600 "$DOSSIER/.env"
# Lire les réglages utiles au déploiement, sans les afficher
valeur_env() { grep -E "^$1=" "$DOSSIER/.env" | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"; }
DB_ENGINE="$(valeur_env DB_ENGINE || true)"

# --------------------------------------------------------------------------------------------
etape "4. Backend : environnement Python et dépendances"
cd "$DOSSIER/backend"
[ -d venv ] || python3 -m venv venv
# shellcheck disable=SC1091
. venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# --------------------------------------------------------------------------------------------
etape "5. Sauvegarde de la base avant les migrations"
mkdir -p "$SAUVEGARDES"
if [ "${DB_ENGINE:-}" = "sqlite" ]; then
  if [ -f db.sqlite3 ]; then
    cp db.sqlite3 "$SAUVEGARDES/ikarama-$HORODATAGE.sqlite3"
    echo "Copie SQLite faite."
  fi
else
  if command -v pg_dump >/dev/null; then
    # Un échec de la sauvegarde arrête le déploiement : pas de migration sans sauvegarde
    PGPASSWORD="$(valeur_env DB_PASSWORD || true)" pg_dump \
      -h "$(valeur_env DB_HOST || echo 127.0.0.1)" -p "$(valeur_env DB_PORT || echo 5432)" \
      -U "$(valeur_env DB_USER || true)" -Fc -f "$SAUVEGARDES/ikarama-$HORODATAGE.dump" "$(valeur_env DB_NAME || true)" \
      || echec "sauvegarde PostgreSQL impossible (vérifiez DB_* dans .env) : migrations non lancées"
    echo "Sauvegarde : $SAUVEGARDES/ikarama-$HORODATAGE.dump"
  else
    echo "pg_dump absent : pas de sauvegarde automatique (installez postgresql-client)."
  fi
fi
chmod 700 "$SAUVEGARDES"
# Garder les 10 dernières sauvegardes
{ ls -1t "$SAUVEGARDES"/ikarama-* 2>/dev/null || true; } | tail -n +11 | xargs -r rm -f

# --------------------------------------------------------------------------------------------
etape "6. Backend : vérifier, migrer, fichiers statiques"
python manage.py check
python manage.py migrate --noinput
python manage.py collectstatic --noinput >/dev/null
deactivate

# --------------------------------------------------------------------------------------------
etape "7. Frontend : dépendances et compilation (réglages VITE_* du .env)"
cd "$DOSSIER/frontend"
npm ci --no-audit --no-fund
npm run build

# --------------------------------------------------------------------------------------------
etape "8. Redémarrage"
if [ -n "$SERVICE" ] && command -v systemctl >/dev/null && systemctl cat "$SERVICE.service" >/dev/null 2>&1; then
  sudo -n systemctl restart "$SERVICE" || echec "redémarrage refusé : ajoutez la règle sudo de docs/CI-CD.md (étape 6)"
  sleep 3
  systemctl is-active --quiet "$SERVICE" || echec "le service $SERVICE ne tourne pas : journalctl -u $SERVICE -n 50"
  echo "Service $SERVICE redémarré."
else
  if [ -z "$SERVICE" ]; then echo "Redémarrage désactivé (IKARAMA_SERVICE vide)."; else echo "Service « $SERVICE » pas encore installé : voir docs/CI-CD.md (étape 5). Code et base sont à jour."; fi
fi

# --------------------------------------------------------------------------------------------
etape "9. Vérification"
if [ -n "$SERVICE" ] && command -v curl >/dev/null && systemctl is-active --quiet "$SERVICE" 2>/dev/null; then
  code="$(curl -s -o /dev/null -w '%{http_code}' "$URL_SANTE" || true)"
  case "$code" in 200|301|302) echo "Ikarama répond ($code sur $URL_SANTE).";;
    *) echec "Ikarama ne répond pas correctement ($code sur $URL_SANTE) : journalctl -u $SERVICE -n 50";; esac
fi

echo "$(date -Iseconds) $(cd "$SOURCE" && git rev-parse --short HEAD 2>/dev/null || echo '?')" >> "$MARQUEUR"
etape "Déploiement terminé dans $DOSSIER"
