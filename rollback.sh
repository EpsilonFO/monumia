#!/bin/bash
#
# Rollback du statique : repointe `current` sur une release précédente.
#
#   ./rollback.sh app            → liste les releases disponibles
#   ./rollback.sh app 5511cec    → bascule app sur cette release
#
# Instantané, puisque les releases sont déjà sur le disque. Ne touche NI aux
# backends NI aux migrations : si le problème vient d'un changement de schéma,
# un rollback du statique ne suffira pas.
set -eo pipefail
cd ~/monumia
source scripts/lib-release.sh

TARGETS="app beta landing landing-beta"

target="${1:-}"
sha="${2:-}"

if [ -z "$target" ] || ! printf '%s\n' $TARGETS | grep -qx "$target"; then
  echo "Usage : ./rollback.sh <cible> [sha]"
  echo "Cibles : $TARGETS"
  exit 1
fi

base="$RELEASE_ROOT/$target"
dir="$base/releases"

if [ ! -d "$dir" ]; then
  echo "❌ Aucune release pour $target ($dir absent)."
  exit 1
fi

current=""
[ -L "$base/current" ] && current=$(basename "$(readlink "$base/current")")

if [ -z "$sha" ]; then
  echo "Releases disponibles pour $target (plus récente en premier) :"
  sudo ls -1t "$dir" | while IFS= read -r r; do
    if [ "$r" = "$current" ]; then echo "  $r  ← en ligne"; else echo "  $r"; fi
  done
  echo
  echo "Pour basculer : ./rollback.sh $target <sha>"
  exit 0
fi

if [ ! -d "$dir/$sha" ]; then
  echo "❌ Release $sha introuvable pour $target."
  echo "   ./rollback.sh $target  pour voir la liste."
  exit 1
fi

if [ ! -f "$dir/$sha/index.html" ]; then
  echo "❌ $dir/$sha ne contient pas d'index.html, bascule refusée."
  exit 1
fi

sudo ln -sfn "releases/$sha" "$base/.current.tmp"
sudo mv -T "$base/.current.tmp" "$base/current"
echo "$target : $current → $sha"

reload_nginx
