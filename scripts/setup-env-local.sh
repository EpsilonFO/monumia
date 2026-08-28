#!/bin/bash
#
# Génère backend/.env.local et frontend/.env.local à partir de la stack Supabase
# locale. Ces deux fichiers sont gitignorés et propres à chaque machine : les clés
# locales sont régénérées par le CLI, il n'y a donc rien à se faire passer entre
# développeurs, et `supabase status` en est la seule source de vérité.
#
# Démarre la stack si elle est arrêtée (idempotent, et `supabase start` applique
# au passage les migrations sur une base vierge).
#
# Usage :
#   ./scripts/setup-env-local.sh            # n'écrase pas un fichier existant
#   ./scripts/setup-env-local.sh --force    # réécrit les deux fichiers
set -eo pipefail

RACINE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RACINE"

FORCE=0
[ "$1" = "--force" ] && FORCE=1

if ! command -v supabase >/dev/null 2>&1; then
  echo "❌ CLI Supabase introuvable — https://supabase.com/docs/guides/cli" >&2
  exit 1
fi

# `status -o env` échoue tant que les conteneurs ne tournent pas.
if ! STATUS="$(supabase status -o env 2>/dev/null)"; then
  echo "Stack locale arrêtée, démarrage (première fois : quelques minutes)..."
  supabase start
  STATUS="$(supabase status -o env)"
fi

lire() {
  # Les valeurs sortent entre guillemets : API_URL="http://127.0.0.1:54321"
  echo "$STATUS" | grep "^$1=" | head -1 | cut -d= -f2- | tr -d '"'
}

API_URL="$(lire API_URL)"
ANON_KEY="$(lire ANON_KEY)"
PUBLISHABLE_KEY="$(lire PUBLISHABLE_KEY)"
SECRET_KEY="$(lire SECRET_KEY)"
SERVICE_ROLE_KEY="$(lire SERVICE_ROLE_KEY)"
JWT_SECRET="$(lire JWT_SECRET)"

for nom in API_URL ANON_KEY PUBLISHABLE_KEY SECRET_KEY SERVICE_ROLE_KEY JWT_SECRET; do
  if [ -z "${!nom}" ]; then
    echo "❌ $nom absent de \`supabase status -o env\` — version de CLI trop ancienne ?" >&2
    exit 1
  fi
done

ecrire() {
  chemin="$1"
  contenu="$2"
  if [ -f "$chemin" ] && [ "$FORCE" -eq 0 ]; then
    echo "↷ $chemin existe déjà, laissé tel quel (--force pour le réécrire)"
    return
  fi
  printf '%s\n' "$contenu" > "$chemin"
  echo "✓ $chemin"
}

ecrire backend/.env.local "$(
  cat <<EOF
# Généré par scripts/setup-env-local.sh — ne pas committer (gitignoré).
# Régénérer après un \`supabase stop\`/\`start\` qui change les clés :
#   ./scripts/setup-env-local.sh --force

SUPABASE_URL=$API_URL
SUPABASE_PUBLISHABLE_KEY=$PUBLISHABLE_KEY
SUPABASE_SECRET_KEY=$SECRET_KEY
# Nom hérité, attendu par backend/scripts/seeds/*.py — même rôle que SECRET_KEY.
SUPABASE_SERVICE_KEY=$SERVICE_ROLE_KEY
# La base locale signe ses JWT en HS256 : sans ce secret, chaque requête
# authentifiée repart valider le token auprès de l'API Auth (cf. db.py).
SUPABASE_JWT_SECRET=$JWT_SECRET

# Expose /docs et /redoc.
ENV=development
# Cookie de refresh sans l'attribut Secure, indispensable en http://localhost.
COOKIE_SECURE=false
FRONTEND_URL=http://localhost:3000
APP_URL=http://localhost:3000
EOF
)"

ecrire frontend/.env.local "$(
  cat <<EOF
# Généré par scripts/setup-env-local.sh — ne pas committer (gitignoré).

VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=$API_URL
VITE_SUPABASE_ANON_KEY=$ANON_KEY
VITE_LANDING_URL=http://localhost:3001
EOF
)"

echo
echo "Supabase local : $API_URL  (Studio : $(lire STUDIO_URL))"
echo "Emails de dev  : $(lire MAILPIT_URL)"
echo
echo "Étape suivante — peupler les référentiels :"
echo "  cd backend && uv run python scripts/seeds/seed_all.py"
