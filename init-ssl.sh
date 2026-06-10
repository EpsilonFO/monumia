#!/bin/bash
# Generate SSL certificates for the monumia.fr domains
#
# Prerequisites:
#   1. DNS A records on OVH pointing to the VPS (51.91.156.208) for:
#      monumia.fr, www.monumia.fr, app.monumia.fr, beta.monumia.fr
#   2. nginx running and serving /.well-known/acme-challenge/ from
#      /var/www/certbot on port 80 (the current config does this for
#      any Host, so no need to switch to nginx-init.conf first)
#
# Usage (on the VPS):
#   bash init-ssl.sh
#   # then deploy the new nginx.conf and restart:
#   docker compose restart nginx

set -e

EMAIL="contact@monumia.fr"

# NB: --entrypoint is required — the certbot service's default entrypoint
# is a `certbot renew` loop that ignores the command passed to `run`.
echo "==> Requesting certificate for monumia.fr + www.monumia.fr..."
docker compose run --rm \
  --entrypoint "certbot certonly --webroot --webroot-path=/var/www/certbot -d monumia.fr -d www.monumia.fr --email $EMAIL --agree-tos --no-eff-email" \
  certbot

for DOMAIN in app.monumia.fr beta.monumia.fr; do
  echo "==> Requesting certificate for $DOMAIN..."
  docker compose run --rm \
    --entrypoint "certbot certonly --webroot --webroot-path=/var/www/certbot -d $DOMAIN --email $EMAIL --agree-tos --no-eff-email" \
    certbot
done

echo "==> Done! Now deploy the new nginx.conf and restart nginx:"
echo "    docker compose restart nginx"
