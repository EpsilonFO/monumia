#!/bin/bash
set -e
cd ~/monumia
git pull

# ── Migrations Supabase (beta) ────────────────────────
# Pousse les migrations de supabase/migrations/ vers le projet beta. La
# connection string Postgres (percent-encodée) doit être dans backend/.env.beta
# sous SUPABASE_DB_URL. `db push` est idempotent. No-op (avec avertissement) si
# le CLI ou la variable manque.
if command -v supabase >/dev/null 2>&1; then
  BETA_DB_URL=$(grep -E '^SUPABASE_DB_URL=' backend/.env.beta 2>/dev/null | head -1 | cut -d= -f2- || true)
  if [ -n "$BETA_DB_URL" ]; then
    echo "Pushing DB migrations (beta)..."
    supabase db push --db-url "$BETA_DB_URL" --yes
  else
    echo "⚠️  SUPABASE_DB_URL absent de backend/.env.beta — migrations IGNORÉES."
  fi
else
  echo "⚠️  supabase CLI introuvable — migrations beta IGNORÉES."
fi

sudo docker stop monumia-nginx monumia-beta-frontend-build monumia-landing-beta-build patrys-nginx patrys-beta-frontend-build 2>/dev/null || true
sudo docker rm -f monumia-beta-frontend-build monumia-landing-beta-build patrys-beta-frontend-build 2>/dev/null || true
sudo docker rm -f $(sudo docker ps -a -q --filter volume=patrys_beta_frontend_dist) 2>/dev/null || true
sudo docker rm -f $(sudo docker ps -a -q --filter volume=patrys_landing_beta_dist) 2>/dev/null || true
sudo docker volume rm -f patrys_beta_frontend_dist patrys_landing_beta_dist
sudo docker compose up -d --build beta-frontend-build beta-backend landing-beta-build
sudo docker compose up -d nginx
echo "Beta deployed! Landing en preview : https://beta.monumia.fr/landing"
