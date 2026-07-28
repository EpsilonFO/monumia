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

push_migrations "beta" backend/.env.beta
push_migrations "prod" backend/.env

echo "Stopping nginx..."
sudo docker stop monumia-nginx 2>/dev/null || true
sudo docker stop patrys-nginx 2>/dev/null || true  # ancien nom, à retirer après la 1re migration

# NB: les volumes restent préfixés patrys_* (nom de projet compose figé
# dans docker-compose.yml) ; seuls les containers s'appellent monumia-*.

# ── Beta cleanup ──────────────────────────────────────
echo "Cleaning beta containers & volumes..."
sudo docker rm -f monumia-beta-frontend-build patrys-beta-frontend-build 2>/dev/null || true
sudo docker rm -f monumia-landing-beta-build 2>/dev/null || true
sudo docker rm -f $(sudo docker ps -a -q --filter volume=patrys_beta_frontend_dist) 2>/dev/null || true
sudo docker rm -f $(sudo docker ps -a -q --filter volume=patrys_landing_beta_dist) 2>/dev/null || true
sudo docker volume rm -f patrys_beta_frontend_dist patrys_landing_beta_dist

# ── Prod cleanup ──────────────────────────────────────
echo "Cleaning prod containers & volumes..."
sudo docker rm -f monumia-app-frontend-build patrys-app-frontend-build 2>/dev/null || true
sudo docker rm -f monumia-landing-build patrys-landing-build 2>/dev/null || true
sudo docker rm -f $(sudo docker ps -a -q --filter volume=patrys_app_frontend_dist) 2>/dev/null || true
sudo docker rm -f $(sudo docker ps -a -q --filter volume=patrys_landing_dist) 2>/dev/null || true
sudo docker volume rm -f patrys_app_frontend_dist
sudo docker volume rm -f patrys_landing_dist

# ── Rebuild everything ────────────────────────────────
echo "Building beta + prod..."
sudo docker compose up -d --build \
  beta-frontend-build beta-backend landing-beta-build \
  app-frontend-build app-backend \
  landing-build

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

echo "Starting nginx..."
sudo docker compose up -d nginx

# ── Récapitulatif ─────────────────────────────────────
echo
echo "─────────────────────────────────────"
echo "  migrations beta : OK"
echo "  migrations prod : OK"
if [ -n "$sync_failures" ]; then
  echo "  sync aides      : ÉCHEC ($sync_failures)"
  echo "─────────────────────────────────────"
  echo "❌ Déployé, mais le sync des aides a échoué."
  echo "   Toute aide présente en YAML mais absente de aides_v3 renverra"
  echo "   « Aide introuvable » à la création de dossier."
  exit 1
fi
echo "  sync aides      : OK"
echo "─────────────────────────────────────"
echo "✅ Beta + Prod déployés."
