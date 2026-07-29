#!/bin/bash
# Generate SSL certificates for the patrialta.fr domains (ancien nom du projet)
#
# À lancer AVANT de déployer le nginx.conf qui référence ces certificats :
# nginx refuse de démarrer si un `ssl_certificate` pointe sur un fichier absent.
#
# Prerequisites:
#   1. DNS A records on OVH pointing to the VPS (51.91.156.208) for:
#      patrialta.fr, www.patrialta.fr, app.patrialta.fr, beta.patrialta.fr
#      (déjà le cas au 29/07/2026)
#   2. nginx running and serving /.well-known/acme-challenge/ from
#      /var/www/certbot on port 80 — le bloc :80 de nginx.conf est le
#      default server du port 80, il répond donc pour n'importe quel Host,
#      y compris patrialta.fr avant l'ajout de ses noms au server_name.
#
# Usage (on the VPS):
#   bash init-ssl-patrialta.sh
#   # puis déployer le nouveau nginx.conf et recharger :
#   docker compose restart nginx

set -e

EMAIL="contact@monumia.fr"

# NB: --entrypoint is required — the certbot service's default entrypoint
# is a `certbot renew` loop that ignores the command passed to `run`.
echo "==> Requesting certificate for patrialta.fr + www.patrialta.fr..."
docker compose run --rm \
  --entrypoint "certbot certonly --webroot --webroot-path=/var/www/certbot -d patrialta.fr -d www.patrialta.fr --email $EMAIL --agree-tos --no-eff-email" \
  certbot

for DOMAIN in app.patrialta.fr beta.patrialta.fr; do
  echo "==> Requesting certificate for $DOMAIN..."
  docker compose run --rm \
    --entrypoint "certbot certonly --webroot --webroot-path=/var/www/certbot -d $DOMAIN --email $EMAIL --agree-tos --no-eff-email" \
    certbot
done

echo "==> Done! Now deploy the new nginx.conf and restart nginx:"
echo "    docker compose restart nginx"
