#!/usr/bin/env bash
# Type check du frontend, utilisable depuis le dépôt principal comme depuis un worktree.
#
# Pourquoi ce script plutôt qu'un `npx tsc -b` direct dans .pre-commit-config.yaml :
# un worktree git n'a pas de frontend/node_modules (le dossier est gitignoré, donc
# jamais recopié). `npx tsc` allait alors chercher sur le registre npm un paquet
# homonyme qui n'est pas TypeScript, échouait, et pre-commit ratait la restauration
# de son stash — l'index se retrouvait vide et le commit suivant enregistrait la
# suppression de tout le dépôt.
set -euo pipefail

racine=$(git rev-parse --show-toplevel)
cd "$racine/frontend"

if [ ! -d node_modules ]; then
  # Dans un worktree, réutiliser les node_modules du dépôt principal.
  # --git-common-dir pointe sur le .git partagé, dont le parent est le dépôt principal.
  principal=$(dirname "$(cd "$racine" && git rev-parse --path-format=absolute --git-common-dir)")
  if [ -d "$principal/frontend/node_modules" ]; then
    ln -s "$principal/frontend/node_modules" node_modules
    echo "node_modules lié depuis $principal/frontend"
  else
    echo "frontend/node_modules introuvable : lancer 'npm ci' dans frontend/" >&2
    exit 1
  fi
fi

# --no-install : ne jamais télécharger un paquet depuis le registre. Sans ce garde-fou,
# une installation incomplète fait silencieusement passer npx sur le mauvais paquet.
exec npx --no-install tsc -b
