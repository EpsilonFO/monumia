#!/bin/bash
set -e
cd ~/patrialta
git pull
docker compose rm -sf beta-frontend-build
docker volume rm -f patrialta_beta_frontend_dist
docker compose up -d --build beta-frontend-build beta-backend
docker compose restart nginx
echo "Beta deployed!"
EOF
chmod +x ~/patrialta/deploy-beta.sh
