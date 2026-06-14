#!/bin/bash
set -e
cd ~/monumia
git pull

# ── Migrations Supabase ───────────────────────────────
# Pousse les migrations de supabase/migrations/ vers le projet ciblé AVANT de
# (re)démarrer les backends, pour que la DB soit prête. La connection string
# Postgres (percent-encodée) doit être dans le .env de l'environnement, sous
# SUPABASE_DB_URL. `db push` est idempotent : seules les migrations non encore
# appliquées sont jouées. No-op (avec avertissement) si le CLI ou la variable
# manque, pour ne pas bloquer le déploiement.
push_migrations() {
  local label="$1" env_file="$2"
  if ! command -v supabase >/dev/null 2>&1; then
    echo "⚠️  supabase CLI introuvable — migrations $label IGNORÉES."
    return 0
  fi
  local db_url
  db_url=$(grep -E '^SUPABASE_DB_URL=' "$env_file" 2>/dev/null | head -1 | cut -d= -f2- || true)
  if [ -z "$db_url" ]; then
    echo "⚠️  SUPABASE_DB_URL absent de $env_file — migrations $label IGNORÉES."
    return 0
  fi
  echo "Pushing DB migrations ($label)..."
  supabase db push --db-url "$db_url" --yes
}

push_migrations "beta" backend/.env.beta
push_migrations "prod" backend/.env

echo "Stopping nginx..."
sudo docker stop monumia-nginx 2>/dev/null || true
sudo docker stop patrys-nginx 2>/dev/null || true  # ancien nom, à retirer après la 1re migration

# NB: les volumes restent préfixés patrys_* (nom de projet compose figé
# dans docker-compose.yml) ; seuls les containers s'appellent monumia-*.

# ── Beta cleanup ──────────────────────────────────────
echo "Cleaning beta containers & volumes..."
sudo docker rm -f monumia-beta-frontend-build patrys-beta-frontend-build 2>/dev/null || true
sudo docker rm -f monumia-landing-beta-build 2>/dev/null || true
sudo docker rm -f $(sudo docker ps -a -q --filter volume=patrys_beta_frontend_dist) 2>/dev/null || true
sudo docker rm -f $(sudo docker ps -a -q --filter volume=patrys_landing_beta_dist) 2>/dev/null || true
sudo docker volume rm -f patrys_beta_frontend_dist patrys_landing_beta_dist

# ── Prod cleanup ──────────────────────────────────────
echo "Cleaning prod containers & volumes..."
sudo docker rm -f monumia-app-frontend-build patrys-app-frontend-build 2>/dev/null || true
sudo docker rm -f monumia-landing-build patrys-landing-build 2>/dev/null || true
sudo docker rm -f $(sudo docker ps -a -q --filter volume=patrys_app_frontend_dist) 2>/dev/null || true
sudo docker rm -f $(sudo docker ps -a -q --filter volume=patrys_landing_dist) 2>/dev/null || true
sudo docker volume rm -f patrys_app_frontend_dist
sudo docker volume rm -f patrys_landing_dist

# ── Rebuild everything ────────────────────────────────
echo "Building beta + prod..."
sudo docker compose up -d --build \
  beta-frontend-build beta-backend landing-beta-build \
  app-frontend-build app-backend \
  landing-build

echo "Starting nginx..."
sudo docker compose up -d nginx

echo "Beta + Prod deployed!"
