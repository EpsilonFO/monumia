#!/bin/bash
set -eo pipefail
cd ~/monumia
git pull

# ── Migrations Supabase (beta) ────────────────────────
# Voir scripts/lib-migrations.sh, partagé avec deploy.sh. Échec dur si le CLI,
# le .env ou la connection string manquent.
source scripts/lib-migrations.sh
source scripts/lib-release.sh
source scripts/lib-deploy.sh

# Les étapes dont l'entrée n'a pas bougé depuis leur dernier succès sont
# sautées : voir scripts/lib-deploy.sh. `FORCE=1 ./beta.sh` refait tout.

SHA=$(git rev-parse --short HEAD)

# Migrations en parallèle du build, attendues avant toute publication : même
# raisonnement que dans deploy.sh.
echo "Migrations beta, en parallèle du build..."
migrer_si_besoin "beta" backend/.env.beta > >(prefixer migrations) 2>&1 &
migrations_pid=$!

# Build à côté, nginx et la prod continuent de servir. Voir scripts/lib-release.sh
# pour le détail de la bascule sans coupure.
echo "Building beta images ($SHA)..."
if ! sudo docker compose build beta-frontend-build landing-beta-build beta-backend; then
  wait "$migrations_pid" || true
  echo "❌ Build en échec : rien n'est publié, le backend beta n'a pas été touché."
  exit 1
fi

if ! wait "$migrations_pid"; then
  echo "❌ Migrations beta en échec : rien n'est publié, le backend beta n'a pas été touché."
  exit 1
fi

echo "Publishing static releases..."
publish_dist beta         monumia-beta-frontend-build "$SHA"
publish_dist landing-beta monumia-landing-beta-build  "$SHA"

echo "Restarting beta backend..."
redemarrer_backends beta-backend

nginx_reload_failed=""
sudo docker compose up -d nginx
reload_nginx || nginx_reload_failed="oui"

# ── Sync aides YAML → aides_v3 (beta) ─────────────────
# Voir sync_aides (scripts/lib-deploy.sh). Le ménage des releases se fait
# pendant qu'il attend le réseau.
echo "Syncing aides YAML → aides_v3 (beta)..."
sync_aides beta monumia-beta-backend > >(prefixer "aides beta") 2>&1 &
sync_pid=$!

prune_releases beta 3
prune_releases landing-beta 3

sync_ok=1
wait "$sync_pid" || sync_ok=0

if [ "$sync_ok" -eq 0 ]; then
  echo "❌ Beta déployée, mais le sync des aides a ÉCHOUÉ."
  echo "   Toute aide présente en YAML mais absente de aides_v3 renverra"
  echo "   « Aide introuvable » à la création de dossier."
  exit 1
fi
if [ -n "$nginx_reload_failed" ]; then
  echo "❌ Beta déployée, mais nginx.conf est invalide et n'a pas été rechargé."
  echo "   nginx tourne toujours avec sa configuration précédente."
  exit 1
fi

echo "✅ Beta déployée ($SHA). Landing en preview : https://beta.monumia.fr/landing"
