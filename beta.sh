#!/bin/bash
set -e
cd ~/patrialta
git pull
sudo docker stop patrialta-nginx patrialta-beta-frontend-build 2>/dev/null || true
sudo docker rm -f patrialta-beta-frontend-build 2>/dev/null || true
sudo docker rm -f $(sudo docker ps -a -q --filter volume=patrialta_beta_frontend_dist) 2>/dev/null || true
sudo docker volume rm -f patrialta_beta_frontend_dist
sudo docker compose up -d --build beta-frontend-build beta-backend
sudo docker compose up -d nginx
echo "Beta deployed!"
