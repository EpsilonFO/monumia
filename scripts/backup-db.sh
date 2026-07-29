#!/bin/bash
#
# Sauvegarde quotidienne de la base de PRODUCTION vers le VPS.
#
# POURQUOI, alors que Supabase sauvegarde déjà
# --------------------------------------------
# Les sauvegardes Supabase vivent DANS le projet : supprimer le projet supprime
# les sauvegardes avec lui, l'opération est irréversible. Elles couvrent la
# table vidée par erreur, pas la perte du projet ou du compte. Ce script est le
# seul exemplaire qui survit à ce scénario.
#
# Rappel : les objets du bucket `documents` NE SONT PAS ici. Le dump n'en
# contient que les métadonnées (lignes de storage.objects). Sauvegarder les
# fichiers eux-mêmes demande une synchronisation séparée du Storage.
#
# CE QUI EST CAPTURÉ
# ------------------
#   roles.sql   les rôles du cluster
#   schema.sql  le DDL
#   data.sql    les données, incluant le schéma `auth` (donc les comptes
#               utilisateurs) et `storage` (métadonnées des documents). Vérifié :
#               la liste --exclude-schema du CLI ne contient ni auth ni storage.
#
# RESTAURATION (à tester au moins une fois, sur un projet vierge)
# ---------------------------------------------------------------
#   tar xzf monumia-prod-AAAA-MM-JJ.tar.gz
#   psql --single-transaction --variable ON_ERROR_STOP=1 \
#        --file roles.sql --file schema.sql \
#        --command 'SET session_replication_role = replica' \
#        --file data.sql --dbname "<connection string du projet cible>"
#
# INSTALLATION DU CRON (crontab de root, pour que /srv soit accessible)
# ---------------------------------------------------------------------
#   sudo crontab -e
#   17 3 * * * /home/<user>/monumia/scripts/backup-db.sh >> /var/log/monumia-backup.log 2>&1
#
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

BACKUP_ROOT="${BACKUP_ROOT:-/srv/monumia-backups}"
KEEP_DAILY="${KEEP_DAILY:-7}"
KEEP_WEEKLY="${KEEP_WEEKLY:-4}"
ALERT_EMAIL="${BACKUP_ALERT_EMAIL:-felixollivier@delosintelligence.fr}"
ALERT_FROM="${BACKUP_ALERT_FROM:-Monumia <invitations@monumia.fr>}"
# Une sauvegarde qui perd plus de la moitié de son poids d'un jour à l'autre est
# suspecte : soit un incident en base, soit un dump tronqué. Dans les deux cas
# on veut être prévenu, et surtout ne pas supprimer les copies précédentes.
SHRINK_PCT="${SHRINK_PCT:-50}"

cd "$REPO_DIR"
source scripts/lib-migrations.sh

DATE=$(date +%F)
DAILY_DIR="$BACKUP_ROOT/daily"
WEEKLY_DIR="$BACKUP_ROOT/weekly"
ARCHIVE="$DAILY_DIR/monumia-prod-$DATE.tar.gz"

# ── Alerte ────────────────────────────────────────────
# Un backup qui casse en silence donne l'illusion d'être couvert, ce qui est
# pire que pas de backup du tout. On passe par Resend, déjà configuré pour les
# emails d'invitation.
alert() {
  local subject="$1" body="$2"
  echo "$body" >&2

  local key
  key=$(sed -nE 's/^RESEND_API_KEY=//p' backend/.env 2>/dev/null | head -1 | tr -d '"'\''\r')
  if [ -z "$key" ]; then
    echo "⚠️  RESEND_API_KEY absent de backend/.env : alerte email non envoyée." >&2
    return 0
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    echo "⚠️  python3 introuvable : alerte email non envoyée." >&2
    return 0
  fi

  local payload
  payload=$(SUBJ="$subject" BODY="$body" FROM="$ALERT_FROM" TO="$ALERT_EMAIL" python3 -c '
import json, os
print(json.dumps({
    "from": os.environ["FROM"],
    "to": [os.environ["TO"]],
    "subject": os.environ["SUBJ"],
    "text": os.environ["BODY"],
}))')

  curl -sS -X POST https://api.resend.com/emails \
    -H "Authorization: Bearer $key" \
    -H "Content-Type: application/json" \
    -d "$payload" >/dev/null \
    || echo "⚠️  envoi de l'alerte Resend échoué." >&2
}

fail() {
  alert "Backup Monumia ÉCHOUÉ ($DATE)" "$1"
  exit 1
}

trap 'fail "Le script de sauvegarde s'\''est interrompu de façon inattendue (ligne $LINENO)."' ERR

# ── Préconditions ─────────────────────────────────────
command -v supabase >/dev/null 2>&1 \
  || fail "supabase CLI introuvable sur le VPS, aucune sauvegarde produite."

DB_URL=$(read_db_url backend/.env || true)
[ -n "$DB_URL" ] \
  || fail "SUPABASE_DB_URL absent de backend/.env, aucune sauvegarde produite."

sudo mkdir -p "$DAILY_DIR" "$WEEKLY_DIR"

# Un dump peut durer plus longtemps que prévu ; deux exécutions concurrentes
# écriraient dans le même répertoire temporaire.
exec 9>"$BACKUP_ROOT/.lock"
if ! flock -n 9; then
  echo "Une sauvegarde est déjà en cours, on sort sans rien faire."
  exit 0
fi

# ── Dump ──────────────────────────────────────────────
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

echo "[$(date +%T)] Dump de la production..."
supabase db dump --db-url "$DB_URL" -f "$TMP/roles.sql"  --role-only
supabase db dump --db-url "$DB_URL" -f "$TMP/schema.sql"
# Les deux tables exclues sont des index vectoriels internes au Storage, non
# restaurables et régénérés par la plateforme.
supabase db dump --db-url "$DB_URL" -f "$TMP/data.sql" --use-copy --data-only \
  -x "storage.buckets_vectors" -x "storage.vector_indexes"

# ── Contrôles de vraisemblance ────────────────────────
# pg_dump peut sortir en code 0 avec un fichier tronqué : on ne fait pas
# confiance au code retour seul.
for f in roles.sql schema.sql data.sql; do
  [ -s "$TMP/$f" ] || fail "Le dump $f est vide. Sauvegarde du $DATE abandonnée."
done

grep -q "CREATE TABLE" "$TMP/schema.sql" \
  || fail "schema.sql ne contient aucun CREATE TABLE. Dump probablement tronqué."
grep -q "^COPY " "$TMP/data.sql" \
  || fail "data.sql ne contient aucune instruction COPY. Dump probablement vide."

# Le CLI émet les identifiants entre guillemets : COPY "auth"."users" (...).
# Le motif tolère les deux formes, au cas où une version future les omette.
grep -qE '^COPY "?auth"?\."?users"?' "$TMP/data.sql" \
  || fail "data.sql ne contient pas auth.users : les comptes utilisateurs ne seraient pas restaurables."
grep -qE '^COPY "?public"?\."?monuments"?' "$TMP/data.sql" \
  || fail "data.sql ne contient pas public.monuments : dump incomplet."

# ── Archive ───────────────────────────────────────────
tar -czf "$TMP/archive.tar.gz" -C "$TMP" roles.sql schema.sql data.sql
tar -tzf "$TMP/archive.tar.gz" >/dev/null \
  || fail "L'archive produite est illisible. Sauvegarde du $DATE abandonnée."

NEW_SIZE=$(stat -c%s "$TMP/archive.tar.gz" 2>/dev/null || stat -f%z "$TMP/archive.tar.gz")

# Comparaison à la dernière sauvegarde connue, AVANT d'écrire la nouvelle.
PREV=$(sudo ls -1t "$DAILY_DIR"/monumia-prod-*.tar.gz 2>/dev/null | head -1 || true)
SHRINK_WARNING=""
if [ -n "$PREV" ]; then
  PREV_SIZE=$(sudo stat -c%s "$PREV" 2>/dev/null || sudo stat -f%z "$PREV")
  if [ "$PREV_SIZE" -gt 0 ] && [ $((NEW_SIZE * 100 / PREV_SIZE)) -lt "$SHRINK_PCT" ]; then
    SHRINK_WARNING="La sauvegarde du $DATE pèse $NEW_SIZE octets contre $PREV_SIZE pour $(basename "$PREV"), soit une chute de plus de $((100 - SHRINK_PCT)) %. L'archive a été conservée et aucune ancienne copie n'a été supprimée : vérifie la base avant de faire confiance à ce fichier."
  fi
fi

sudo cp "$TMP/archive.tar.gz" "$ARCHIVE"
sudo chmod 600 "$ARCHIVE"
echo "[$(date +%T)] Écrit : $ARCHIVE ($NEW_SIZE octets)"

# ── Copie hebdomadaire (dimanche) ─────────────────────
# Lien physique : la copie ne coûte rien tant que la quotidienne existe encore,
# et survit à sa purge.
if [ "$(date +%u)" = "7" ]; then
  sudo ln -f "$ARCHIVE" "$WEEKLY_DIR/monumia-prod-$DATE.tar.gz"
  echo "[$(date +%T)] Copie hebdomadaire créée."
fi

# ── Rotation ──────────────────────────────────────────
# Sautée si la taille est suspecte : on ne purge pas les bonnes copies sur la
# foi d'un dump douteux.
if [ -n "$SHRINK_WARNING" ]; then
  alert "Backup Monumia SUSPECT ($DATE)" "$SHRINK_WARNING"
  echo "⚠️  Rotation sautée, anciennes sauvegardes conservées."
  exit 1
fi

prune() {
  local dir="$1" keep="$2" old
  while IFS= read -r old; do
    [ -z "$old" ] && continue
    sudo rm -f "$old"
    echo "   purgé : $(basename "$old")"
  done < <(sudo ls -1t "$dir"/monumia-prod-*.tar.gz 2>/dev/null | tail -n +$((keep + 1)))
}

prune "$DAILY_DIR" "$KEEP_DAILY"
prune "$WEEKLY_DIR" "$KEEP_WEEKLY"

trap - ERR
echo "[$(date +%T)] ✅ Sauvegarde terminée. $KEEP_DAILY quotidiennes, $KEEP_WEEKLY hebdomadaires conservées."
