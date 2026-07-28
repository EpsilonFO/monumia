#!/bin/bash
set -eo pipefail
cd ~/monumia
git pull

# ── Migrations Supabase (beta) ────────────────────────
# Voir scripts/lib-migrations.sh, partagé avec deploy.sh. Échec dur si le CLI,
# le .env ou la connection string manquent.
source scripts/lib-migrations.sh

push_migrations "beta" backend/.env.beta

sudo docker stop monumia-nginx monumia-beta-frontend-build monumia-landing-beta-build patrys-nginx patrys-beta-frontend-build 2>/dev/null || true
sudo docker rm -f monumia-beta-frontend-build monumia-landing-beta-build patrys-beta-frontend-build 2>/dev/null || true
sudo docker rm -f $(sudo docker ps -a -q --filter volume=patrys_beta_frontend_dist) 2>/dev/null || true
sudo docker rm -f $(sudo docker ps -a -q --filter volume=patrys_landing_beta_dist) 2>/dev/null || true
sudo docker volume rm -f patrys_beta_frontend_dist patrys_landing_beta_dist
sudo docker compose up -d --build beta-frontend-build beta-backend landing-beta-build

# ── Sync aides YAML → aides_v3 (beta) ─────────────────
# Même raison que dans deploy.sh : sans ce sync, une aide ajoutée en YAML mais
# absente de aides_v3 renvoie « Aide introuvable » à la création de dossier.
# Ce script ne le faisait pas, donc un déploiement beta seul laissait la table
# en retard sur les YAML. Idempotent (upsert par slug).
echo "Syncing aides YAML → aides_v3 (beta)..."
sync_ok=1
sudo docker exec monumia-beta-backend uv run python scripts/load_aides_yaml.py || sync_ok=0

sudo docker compose up -d nginx

if [ "$sync_ok" -eq 0 ]; then
  echo "❌ Beta déployée, mais le sync des aides a ÉCHOUÉ."
  echo "   Toute aide présente en YAML mais absente de aides_v3 renverra"
  echo "   « Aide introuvable » à la création de dossier."
  exit 1
fi

echo "✅ Beta déployée. Landing en preview : https://beta.monumia.fr/landing"
