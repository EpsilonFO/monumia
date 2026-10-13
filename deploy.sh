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
source scripts/lib-deploy.sh

# Les étapes dont l'entrée n'a pas bougé depuis leur dernier succès sont
# sautées (migrations, sync des aides, redémarrage des backends) : voir
# scripts/lib-deploy.sh. `FORCE=1 ./deploy.sh` refait tout.

# ── Tout déployer sauf la landing de PROD ─────────────
#
#   SKIP_LANDING_PROD=1 ./deploy.sh
#
# monumia.fr reste alors sur la release qu'il sert déjà : son bundle n'est pas
# construit et, surtout, son lien `current` n'est pas rebasculé. Tout le reste
# part normalement — app.monumia.fr, la beta, la landing beta (donc la landing
# reste vérifiable sous beta.monumia.fr/landing), les backends, les migrations,
# nginx. Rien n'est mémorisé sur l'hôte : le déploiement suivant, sans le
# drapeau, remet monumia.fr au niveau du dépôt.
SKIP_LANDING_PROD="${SKIP_LANDING_PROD:-}"

SHA=$(git rev-parse --short HEAD)

# ── Migrations, en parallèle du build ─────────────────
# Les builds n'ont pas besoin de la base, ni les migrations des images : les
# deux tournent ensemble. Rien n'est publié ni redémarré avant la fin des
# migrations, donc vu de l'extérieur l'ordre reste le même : schéma d'abord,
# code ensuite. Beta puis prod, et la prod n'est pas tentée si la beta échoue.
echo "Migrations (beta puis prod), en parallèle du build..."
(
  migrer_si_besoin "beta" backend/.env.beta || exit 1
  migrer_si_besoin "prod" backend/.env || exit 1
) > >(prefixer migrations) 2>&1 &
migrations_pid=$!

# ── Build ─────────────────────────────────────────────
# Toute la construction se fait pendant que nginx et les backends servent
# normalement. C'est l'essentiel du gain : les ~90 s de builds vite ne sont
# plus dans la fenêtre de coupure, elles sont à côté.
build_targets=(
  app-frontend-build beta-frontend-build
  landing-beta-build
  app-backend beta-backend
)
# `if` et non `[ … ] && …` : sous `set -e`, un test faux en fin de liste
# suffirait à arrêter le déploiement.
if [ -z "$SKIP_LANDING_PROD" ]; then
  build_targets+=(landing-build)
fi

echo "Building images ($SHA)..."
if ! sudo docker compose build "${build_targets[@]}"; then
  wait "$migrations_pid" || true
  echo "❌ Build en échec : rien n'est publié, les backends n'ont pas été touchés."
  exit 1
fi

if ! wait "$migrations_pid"; then
  echo "❌ Migrations en échec : rien n'est publié, les backends n'ont pas été touchés."
  exit 1
fi

# ── Publication du statique ───────────────────────────
# Extraction de /dist hors des images vers /srv/monumia/<cible>/releases/<sha>,
# puis bascule atomique du lien `current`. nginx ne s'arrête pas.
echo "Publishing static releases..."
publish_dist app          monumia-app-frontend-build  "$SHA"
publish_dist beta         monumia-beta-frontend-build "$SHA"
publish_dist landing-beta monumia-landing-beta-build  "$SHA"
if [ -z "$SKIP_LANDING_PROD" ]; then
  publish_dist landing    monumia-landing-build       "$SHA"
else
  echo "   landing → inchangée (SKIP_LANDING_PROD)"
fi

# ── Backends ──────────────────────────────────────────
# Seul point de coupure restant : la recréation des conteneurs backend, soit
# 2 à 4 s de 502 sur /api/ pendant le démarrage de uvicorn. Le statique continue
# d'être servi. Elle n'a lieu que si le code backend a changé depuis le dernier
# redémarrage (ou l'image, ou le .env) : voir redemarrer_backends.
echo "Restarting backends..."
redemarrer_backends app-backend beta-backend

# ── nginx ─────────────────────────────────────────────
# `up -d` est un no-op s'il tourne déjà avec la bonne config. Il ne recrée le
# conteneur que si docker-compose.yml a changé. certbot est relancé au passage :
# si sa boucle de renouvellement est morte, rien d'autre ne le remarquerait
# avant l'expiration des certificats.
nginx_reload_failed=""
sudo docker compose up -d nginx certbot
reload_nginx || nginx_reload_failed="oui"

# ── Sync aides YAML → aides_v3 ────────────────────────
# Voir sync_aides (scripts/lib-deploy.sh). Beta et prod sont deux bases
# distinctes : les deux syncs tournent en parallèle, et le ménage des releases
# et du cache Docker se fait pendant qu'ils attendent le réseau.
#
# Un échec ici n'interrompt pas le déploiement (on veut rendre la main à nginx
# dans tous les cas), mais il est mémorisé et ressort en code de sortie non nul,
# pour ne pas se perdre dans le défilement des logs Docker.
echo "Syncing aides YAML → aides_v3 (beta + prod, en parallèle)..."
sync_aides beta monumia-beta-backend > >(prefixer "aides beta") 2>&1 &
sync_beta_pid=$!
sync_aides prod monumia-app-backend > >(prefixer "aides prod") 2>&1 &
sync_prod_pid=$!

# ── Nettoyage des anciennes releases ──────────────────
# On en garde 3 par cible, plus celle en ligne : de quoi revenir en arrière
# plusieurs fois sans laisser le disque se remplir.
for target in app beta landing landing-beta; do
  prune_releases "$target" 3
done

# ── Nettoyage du cache de build Docker ────────────────
# Chaque déploiement reconstruisait quatre bundles vite plus une image backend
# qui embarquait tout backend/, et rien ne purgeait jamais : 503 entrées et
# 33 Go de cache s'étaient accumulés, sur un disque de 72 Go. On garde 7 jours,
# de quoi servir les déploiements de la semaine sans laisser la place se
# remplir indéfiniment.
echo "Pruning Docker build cache (>7j)..."
sudo docker builder prune -f --filter until=168h 2>&1 | tail -1

sync_failures=""
wait "$sync_beta_pid" || sync_failures="$sync_failures beta"
wait "$sync_prod_pid" || sync_failures="$sync_failures prod"

# ── Récapitulatif ─────────────────────────────────────
echo
echo "─────────────────────────────────────"
echo "  release         : $SHA"
echo "  migrations      : à jour (beta + prod)"
if [ -n "$SKIP_LANDING_PROD" ]; then
  echo "  landing prod    : INCHANGÉE (SKIP_LANDING_PROD)"
fi
[ -n "$sync_failures" ] && echo "  sync aides      : ÉCHEC ($sync_failures)" || echo "  sync aides      : à jour"
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
