#!/bin/bash
set -e
cd ~/monumia
git pull

echo "Stopping nginx..."
sudo docker stop monumia-nginx 2>/dev/null || true
sudo docker stop patrys-nginx 2>/dev/null || true  # ancien nom, à retirer après la 1re migration

# NB: les volumes restent préfixés patrys_* (nom de projet compose figé
# dans docker-compose.yml) ; seuls les containers s'appellent monumia-*.

# ── Beta cleanup ──────────────────────────────────────
echo "Cleaning beta containers & volumes..."
sudo docker rm -f monumia-beta-frontend-build patrys-beta-frontend-build 2>/dev/null || true
sudo docker rm -f $(sudo docker ps -a -q --filter volume=patrys_beta_frontend_dist) 2>/dev/null || true
sudo docker volume rm -f patrys_beta_frontend_dist

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
  beta-frontend-build beta-backend \
  app-frontend-build app-backend \
  landing-build

echo "Starting nginx..."
sudo docker compose up -d nginx

echo "Beta + Prod deployed!"
