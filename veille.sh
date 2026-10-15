#!/usr/bin/env bash
# Lance un passage de veille du catalogue, à la main.
#
#   ./veille.sh                  toutes les aides
#   ./veille.sh 77-festivals     seulement ces aides (un ou plusieurs slugs)
#   ./veille.sh --a-blanc        sans rien écrire (les modèles sont quand même appelés)
#
# Écrit directement dans le working tree : pas de commit pendant qu'elle tourne.
# À la fin : le chemin du rapport, les issues, les durées par étape. Ensuite,
# relire `git diff -- backend/data`, committer, puis `load_aides_yaml.py`.
# Le terminal reste muet pendant la collecte et le traitement : tout est aussi
# écrit dans le journal de la commande, dont le chemin s'affiche au départ.

set -euo pipefail

cd "$(dirname "$0")/backend"
mkdir -p .cache/catalogue/logs
log=".cache/catalogue/logs/veille-$(date +%Y-%m-%d-%H%M).log"
echo "Veille lancée à $(date +%H:%M). Journal de la commande : backend/$log"

uv run --no-sync --env-file .env.local python -m catalogue veille \
  --journal data/catalogue/journal "$@" 2>&1 | tee "$log"
