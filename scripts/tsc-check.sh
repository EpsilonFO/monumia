#!/usr/bin/env bash
# Type check des paquets TypeScript du dépôt (frontend et landing), utilisable
# depuis le dépôt principal comme depuis un worktree.
#
# landing est inclus parce que son seul type check était jusqu'ici le
# `npm run build` du Dockerfile : une erreur y passait pre-commit ET la CI, et
# ne sortait qu'au build Docker d'un déploiement (cf. TS6133 sur LegalPages).
#
# Pourquoi ce script plutôt qu'un `npx tsc -b` direct dans .pre-commit-config.yaml :
# un worktree git n'a pas de node_modules (le dossier est gitignoré, donc
# jamais recopié). `npx tsc` allait alors chercher sur le registre npm un paquet
# homonyme qui n'est pas TypeScript, échouait, et pre-commit ratait la restauration
# de son stash — l'index se retrouvait vide et le commit suivant enregistrait la
# suppression de tout le dépôt.
set -euo pipefail

racine=$(git rev-parse --show-toplevel)

verifier() {
  local paquet=$1
  cd "$racine/$paquet"

  if [ ! -d node_modules ]; then
    # Dans un worktree, réutiliser les node_modules du dépôt principal.
    # --git-common-dir pointe sur le .git partagé, dont le parent est le dépôt principal.
    local principal
    principal=$(dirname "$(cd "$racine" && git rev-parse --path-format=absolute --git-common-dir)")
    if [ -d "$principal/$paquet/node_modules" ]; then
      ln -s "$principal/$paquet/node_modules" node_modules
      echo "node_modules lié depuis $principal/$paquet"
    else
      echo "$paquet/node_modules introuvable : lancer 'npm ci' dans $paquet/" >&2
      exit 1
    fi
  fi

  echo "tsc -b $paquet"
  # --no-install : ne jamais télécharger un paquet depuis le registre. Sans ce garde-fou,
  # une installation incomplète fait silencieusement passer npx sur le mauvais paquet.
  npx --no-install tsc -b
}

for paquet in frontend landing; do
  verifier "$paquet"
done
