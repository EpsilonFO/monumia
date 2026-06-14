#!/bin/bash
set -e
cd ~/monumia
git pull
sudo docker stop monumia-nginx monumia-beta-frontend-build monumia-landing-beta-build patrys-nginx patrys-beta-frontend-build 2>/dev/null || true
sudo docker rm -f monumia-beta-frontend-build monumia-landing-beta-build patrys-beta-frontend-build 2>/dev/null || true
sudo docker rm -f $(sudo docker ps -a -q --filter volume=patrys_beta_frontend_dist) 2>/dev/null || true
sudo docker rm -f $(sudo docker ps -a -q --filter volume=patrys_landing_beta_dist) 2>/dev/null || true
sudo docker volume rm -f patrys_beta_frontend_dist patrys_landing_beta_dist
sudo docker compose up -d --build beta-frontend-build beta-backend landing-beta-build
sudo docker compose up -d nginx
echo "Beta deployed! Landing en preview : https://beta.monumia.fr/landing"
