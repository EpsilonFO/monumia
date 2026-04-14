#!/bin/bash
set -e
cd ~/patrialta
git pull

echo "Stopping nginx..."
sudo docker stop patrialta-nginx 2>/dev/null || true

# ── Beta cleanup ──────────────────────────────────────
echo "Cleaning beta containers & volumes..."
sudo docker rm -f patrialta-beta-frontend-build 2>/dev/null || true
sudo docker rm -f $(sudo docker ps -a -q --filter volume=patrialta_beta_frontend_dist) 2>/dev/null || true
sudo docker volume rm -f patrialta_beta_frontend_dist

# ── Prod cleanup ──────────────────────────────────────
echo "Cleaning prod containers & volumes..."
sudo docker rm -f patrialta-app-frontend-build 2>/dev/null || true
sudo docker rm -f patrialta-landing-build 2>/dev/null || true
sudo docker rm -f $(sudo docker ps -a -q --filter volume=patrialta_app_frontend_dist) 2>/dev/null || true
sudo docker rm -f $(sudo docker ps -a -q --filter volume=patrialta_landing_dist) 2>/dev/null || true
sudo docker volume rm -f patrialta_app_frontend_dist
sudo docker volume rm -f patrialta_landing_dist

# ── Rebuild everything ────────────────────────────────
echo "Building beta + prod..."
sudo docker compose up -d --build \
  beta-frontend-build beta-backend \
  app-frontend-build app-backend \
  landing-build

echo "Starting nginx..."
sudo docker compose up -d nginx

echo "Beta + Prod deployed!"
