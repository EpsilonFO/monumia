#!/bin/bash
set -eo pipefail
cd ~/monumia
git pull

# ── Migrations Supabase (beta) ────────────────────────
# Voir scripts/lib-migrations.sh, partagé avec deploy.sh. Échec dur si le CLI,
# le .env ou la connection string manquent.
source scripts/lib-migrations.sh
source scripts/lib-release.sh

push_migrations "beta" backend/.env.beta

SHA=$(git rev-parse --short HEAD)

# Build à côté, nginx et la prod continuent de servir. Voir scripts/lib-release.sh
# pour le détail de la bascule sans coupure.
echo "Building beta images ($SHA)..."
sudo docker compose build beta-frontend-build landing-beta-build beta-backend

echo "Publishing static releases..."
publish_dist beta         monumia-beta-frontend-build "$SHA"
publish_dist landing-beta monumia-landing-beta-build  "$SHA"

echo "Restarting beta backend..."
sudo docker compose up -d --no-deps beta-backend

nginx_reload_failed=""
sudo docker compose up -d nginx
reload_nginx || nginx_reload_failed="oui"

# ── Sync aides YAML → aides_v3 (beta) ─────────────────
# Même raison que dans deploy.sh : sans ce sync, une aide ajoutée en YAML mais
# absente de aides_v3 renvoie « Aide introuvable » à la création de dossier.
# Ce script ne le faisait pas, donc un déploiement beta seul laissait la table
# en retard sur les YAML. Idempotent (upsert par slug).
echo "Syncing aides YAML → aides_v3 (beta)..."
sync_ok=1
sudo docker exec monumia-beta-backend uv run python scripts/load_aides_yaml.py || sync_ok=0

prune_releases beta 3
prune_releases landing-beta 3

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
