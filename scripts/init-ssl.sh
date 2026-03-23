#!/bin/bash
# Script to initialize SSL certificates for patrialta.fr
# Run this ONCE on your VPS after the first deployment

set -e

DOMAIN="patrialta.fr"
EMAIL="contact@patrialta.fr"  # Change this to your email

echo "=== Step 1: Start with HTTP-only config ==="
cp nginx/nginx-init.conf nginx/nginx.conf.bak
cp nginx/nginx-init.conf nginx/nginx.conf

echo "=== Step 2: Build and start containers ==="
docker compose up -d --build

echo "=== Step 3: Wait for nginx to be ready ==="
sleep 5

echo "=== Step 4: Request certificate from Let's Encrypt ==="
docker compose run --rm --entrypoint "certbot certonly --webroot --webroot-path=/var/www/certbot --email $EMAIL --agree-tos --no-eff-email -d $DOMAIN -d www.$DOMAIN" certbot

echo "=== Step 5: Switch to HTTPS config ==="
cp nginx/nginx.conf.bak nginx/nginx.conf 2>/dev/null || true
# Restore the full SSL config
cat > nginx/nginx.conf << 'NGINX'
server {
    listen 80;
    listen [::]:80;
    server_name patrialta.fr www.patrialta.fr;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name patrialta.fr www.patrialta.fr;

    ssl_certificate /etc/letsencrypt/live/patrialta.fr/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/patrialta.fr/privkey.pem;

    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX

echo "=== Step 6: Reload nginx with SSL ==="
docker compose exec nginx nginx -s reload

echo ""
echo "Done! https://patrialta.fr should now be live."
