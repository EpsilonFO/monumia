#!/bin/bash
set -e
cd ~/patrialta
git pull
sudo docker compose down --remove-orphans
sudo docker volume rm -f patrialta_beta_frontend_dist
sudo docker compose up -d --build
echo "Beta deployed!"
