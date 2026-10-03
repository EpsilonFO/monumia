#!/bin/bash
#
# Rappels quotidiens sur les aides (échéances qui approchent, guichets qui
# ouvrent). Lance backend/scripts/rappels_aides.py DANS le conteneur backend :
# c'est lui qui porte les dépendances Python, le .env et les YAML d'aides.
#
# POURQUOI UN CRON D'HÔTE PLUTÔT QU'UN ORDONNANCEUR DANS L'APP
# ------------------------------------------------------------
# Le backend tourne en `restart: unless-stopped` et se redéploie plusieurs fois
# par semaine. Un scheduler embarqué repartirait à zéro à chaque redémarrage,
# et se dédoublerait le jour où l'on montera un second worker. Le cron d'hôte
# ne dépend d'aucun de ces deux aléas.
#
# INSTALLATION (crontab de root, comme scripts/backup-db.sh)
# ----------------------------------------------------------
#   sudo crontab -e
#   0 9 * * * /home/<user>/monumia/scripts/cron-rappels.sh >> /var/log/monumia-rappels.log 2>&1
#
# L'heure est celle du serveur : vérifier `timedatectl` et poser
# `CRON_TZ=Europe/Paris` en tête de crontab si l'hôte est en UTC, sinon les
# rappels partiront à 11 h l'été.
#
# UTILISATION
# -----------
#   ./scripts/cron-rappels.sh                 # prod
#   ./scripts/cron-rappels.sh beta            # beta
#   ./scripts/cron-rappels.sh prod --dry-run  # n'envoie rien, n'écrit rien
#
set -eo pipefail

CIBLE="${1:-prod}"
shift || true

case "$CIBLE" in
  prod) CONTENEUR="monumia-app-backend" ;;
  beta) CONTENEUR="monumia-beta-backend" ;;
  *)
    echo "Cible inconnue : $CIBLE (attendu : prod | beta)" >&2
    exit 2
    ;;
esac

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTENEUR"; then
  echo "❌ Conteneur $CONTENEUR non démarré — aucun rappel envoyé." >&2
  exit 1
fi

echo "── Rappels d'aides ($CIBLE, $(date +'%F %T')) ──"
docker exec "$CONTENEUR" uv run python scripts/rappels_aides.py "$@"
