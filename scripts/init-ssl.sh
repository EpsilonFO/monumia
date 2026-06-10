#!/bin/bash
# Script to initialize SSL certificates for monumia.fr
# Run this ONCE on your VPS after the first deployment
# (legacy bootstrap — for adding certs to an already-running stack, use ../init-ssl.sh)

set -e

DOMAIN="monumia.fr"
EMAIL="contact@monumia.fr"

echo "=== Step 1: Start with HTTP-only config ==="
cp nginx/nginx.conf nginx/nginx.conf.bak
cp nginx/nginx-init.conf nginx/nginx.conf

echo "=== Step 2: Build and start containers ==="
docker compose up -d --build

echo "=== Step 3: Wait for nginx to be ready ==="
sleep 5

echo "=== Step 4: Request certificate from Let's Encrypt ==="
docker compose run --rm --entrypoint "certbot certonly --webroot --webroot-path=/var/www/certbot --email $EMAIL --agree-tos --no-eff-email -d $DOMAIN -d www.$DOMAIN" certbot

echo "=== Step 5: Restore the full SSL config ==="
cp nginx/nginx.conf.bak nginx/nginx.conf

echo "=== Step 6: Reload nginx with SSL ==="
docker compose exec nginx nginx -s reload

echo ""
echo "Done! https://monumia.fr should now be live."
