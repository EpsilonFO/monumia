#!/bin/bash
set -eo pipefail
cd ~/monumia
git pull

# ── Migrations Supabase ───────────────────────────────
# Voir scripts/lib-migrations.sh. Échec dur si le CLI, le .env ou la
# connection string manquent : on refuse de déployer plutôt que de laisser
# tourner un backend sur un schéma périmé.
#
# NB: beta et prod sont migrées dans la foulée l'une de l'autre, donc la beta
# n'est pas un vrai filet de sécurité pour le schéma prod. Découpler les deux
# (un argument beta|prod|all) reste à faire.
source scripts/lib-migrations.sh
source scripts/lib-release.sh

push_migrations "beta" backend/.env.beta
push_migrations "prod" backend/.env

SHA=$(git rev-parse --short HEAD)

# ── Build ─────────────────────────────────────────────
# Toute la construction se fait pendant que nginx et les backends servent
# normalement. C'est l'essentiel du gain : les ~90 s de builds vite ne sont
# plus dans la fenêtre de coupure, elles sont à côté.
echo "Building images ($SHA)..."
sudo docker compose build \
  app-frontend-build beta-frontend-build \
  landing-build landing-beta-build \
  app-backend beta-backend

# ── Publication du statique ───────────────────────────
# Extraction de /dist hors des images vers /srv/monumia/<cible>/releases/<sha>,
# puis bascule atomique du lien `current`. nginx ne s'arrête pas.
echo "Publishing static releases..."
publish_dist app          monumia-app-frontend-build  "$SHA"
publish_dist beta         monumia-beta-frontend-build "$SHA"
publish_dist landing      monumia-landing-build       "$SHA"
publish_dist landing-beta monumia-landing-beta-build  "$SHA"

# ── Backends ──────────────────────────────────────────
# Seul point de coupure restant : la recréation des conteneurs backend, soit
# 2 à 4 s de 502 sur /api/ pendant le démarrage de uvicorn. Le statique continue
# d'être servi. Si l'image n'a pas changé, compose ne recrée rien et il n'y a
# aucune coupure du tout (le code Python vient du bind mount ./backend:/app,
# donc `git pull` suffit à le mettre à jour).
echo "Restarting backends..."
sudo docker compose up -d --no-deps app-backend beta-backend

# ── nginx ─────────────────────────────────────────────
# `up -d` est un no-op s'il tourne déjà avec la bonne config. Il ne recrée le
# conteneur que si docker-compose.yml a changé.
nginx_reload_failed=""
sudo docker compose up -d nginx
reload_nginx || nginx_reload_failed="oui"

# ── Sync aides YAML → aides_v3 ────────────────────────
# Git est la source de vérité des aides ; le moteur déterministe les sert depuis
# les YAML (id = slug) mais la création de dossier (POST /api/dossiers) résout le
# slug dans aides_v3. Sans ce sync, toute aide ajoutée en YAML mais absente de
# aides_v3 renvoie « Aide introuvable » à la création. Idempotent (upsert par slug).
#
# Un échec ici n'interrompt pas le déploiement (on veut rendre la main à nginx
# dans tous les cas), mais il est mémorisé et ressort en code de sortie non nul,
# pour ne pas se perdre dans le défilement des logs Docker.
sync_failures=""
sync_aides() {
  local label="$1" container="$2"
  if sudo docker exec "$container" uv run python scripts/load_aides_yaml.py; then
    echo "   sync aides $label : OK"
  else
    echo "   sync aides $label : ÉCHEC"
    sync_failures="$sync_failures $label"
  fi
}

echo "Syncing aides YAML → aides_v3 (beta + prod)..."
sync_aides beta monumia-beta-backend
sync_aides prod monumia-app-backend

# ── Nettoyage des anciennes releases ──────────────────
# On en garde 3 par cible, plus celle en ligne : de quoi revenir en arrière
# plusieurs fois sans laisser le disque se remplir.
for target in app beta landing landing-beta; do
  prune_releases "$target" 3
done

# ── Récapitulatif ─────────────────────────────────────
echo
echo "─────────────────────────────────────"
echo "  release         : $SHA"
echo "  migrations beta : OK"
echo "  migrations prod : OK"
[ -n "$sync_failures" ] && echo "  sync aides      : ÉCHEC ($sync_failures)" || echo "  sync aides      : OK"
[ -n "$nginx_reload_failed" ] && echo "  nginx           : reload REFUSÉ" || echo "  nginx           : OK"
echo "─────────────────────────────────────"

if [ -n "$sync_failures" ]; then
  echo "❌ Déployé, mais le sync des aides a échoué."
  echo "   Toute aide présente en YAML mais absente de aides_v3 renverra"
  echo "   « Aide introuvable » à la création de dossier."
  exit 1
fi
if [ -n "$nginx_reload_failed" ]; then
  echo "❌ Déployé, mais nginx.conf est invalide et n'a pas été rechargé."
  echo "   nginx tourne toujours avec sa configuration précédente."
  exit 1
fi
echo "✅ Beta + Prod déployés ($SHA)."
echo "   Rollback : ./rollback.sh app|beta|landing|landing-beta"
