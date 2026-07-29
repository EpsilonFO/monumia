# shellcheck shell=bash
#
# Helper partagé par deploy.sh (beta + prod) et beta.sh (beta seule).
# Vit dans un fichier unique pour que les deux scripts ne puissent pas diverger.
#
# Pousse les migrations de supabase/migrations/ vers le projet ciblé AVANT de
# (re)démarrer les backends, pour que la DB soit prête. La connection string
# Postgres (percent-encodée) doit être dans le .env de l'environnement, sous
# SUPABASE_DB_URL. `db push` est idempotent : seules les migrations non encore
# appliquées sont jouées.
#
# Toute anomalie est un ÉCHEC DUR, avant qu'on touche aux containers. Une
# version précédente se contentait d'un avertissement puis continuait : la beta
# tournait alors sur un schéma périmé sans que rien ne le signale, et le script
# annonçait quand même un déploiement réussi. Mieux vaut refuser de déployer.
#
# Usage : push_migrations <label> <chemin/vers/.env>

# read_db_url <chemin/vers/.env>
#
# Écrit SUPABASE_DB_URL sur stdout, ou retourne non zéro si le fichier ou la
# variable manquent. Utilisé par push_migrations et par backup-db.sh, pour que
# la connection string ne soit parsée qu'à un seul endroit.
#
# sed plutôt que `cut -d= -f2-` : préserve les '=' internes à la valeur. On
# tolère guillemets et CRLF, que le parsing précédent laissait passer dans
# l'URL (échec de connexion parfaitement opaque à l'arrivée).
read_db_url() {
  local env_file="$1"
  [ -f "$env_file" ] || return 1

  local db_url
  db_url=$(sed -nE 's/^SUPABASE_DB_URL=//p' "$env_file" | head -1)
  db_url="${db_url%$'\r'}"
  db_url="${db_url%\"}"; db_url="${db_url#\"}"
  db_url="${db_url%\'}"; db_url="${db_url#\'}"

  [ -n "$db_url" ] || return 1
  printf '%s' "$db_url"
}

push_migrations() {
  local label="$1" env_file="$2"

  if ! command -v supabase >/dev/null 2>&1; then
    echo "❌ supabase CLI introuvable : impossible de migrer $label."
    echo "   Installation : https://supabase.com/docs/guides/cli"
    exit 1
  fi

  if [ ! -f "$env_file" ]; then
    echo "❌ $env_file introuvable : impossible de migrer $label."
    exit 1
  fi

  local db_url
  db_url=$(read_db_url "$env_file" || true)

  if [ -z "$db_url" ]; then
    echo "❌ SUPABASE_DB_URL absent ou vide dans $env_file : migrations $label impossibles."
    echo "   Dashboard Supabase → Connect → URI, session pooler (port 5432)."
    echo "   Mot de passe percent-encodé, sans guillemets ni commentaire en fin de ligne."
    exit 1
  fi

  echo "Pushing DB migrations ($label)..."
  supabase db push --db-url "$db_url" --yes
}
