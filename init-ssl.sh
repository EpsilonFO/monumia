#!/bin/bash
# Generate SSL certificates for new subdomains
# Run this on the VPS after deploying with nginx-init.conf
#
# Prerequisites:
#   1. DNS A records for app.patrialta.fr and beta.patrialta.fr pointing to your VPS
#   2. nginx running with nginx-init.conf (HTTP only)
#
# Usage:
#   1. Copy nginx-init.conf as the active config:
#      cp nginx/nginx-init.conf nginx/nginx.conf
#   2. Start services: docker compose up -d
#   3. Run this script: bash init-ssl.sh
#   4. Restore the full nginx config:
#      cp nginx/nginx.conf.bak nginx/nginx.conf  (or git checkout nginx/nginx.conf)
#   5. Restart nginx: docker compose restart nginx

set -e

echo "==> Requesting certificate for app.patrialta.fr..."
docker compose run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  -d app.patrialta.fr \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email

echo "==> Requesting certificate for beta.patrialta.fr..."
docker compose run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  -d beta.patrialta.fr \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email

echo "==> Done! Now restore nginx.conf and restart nginx:"
echo "    docker compose restart nginx"
