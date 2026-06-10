#!/bin/bash
set -e
cd ~/monumia
git pull
sudo docker stop monumia-nginx monumia-beta-frontend-build patrys-nginx patrys-beta-frontend-build 2>/dev/null || true
sudo docker rm -f monumia-beta-frontend-build patrys-beta-frontend-build 2>/dev/null || true
sudo docker rm -f $(sudo docker ps -a -q --filter volume=patrys_beta_frontend_dist) 2>/dev/null || true
sudo docker volume rm -f patrys_beta_frontend_dist
sudo docker compose up -d --build beta-frontend-build beta-backend
sudo docker compose up -d nginx
echo "Beta deployed!"
