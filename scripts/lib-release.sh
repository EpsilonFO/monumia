# shellcheck shell=bash
#
# Publication du statique (frontends + landings) sans downtime.
#
# POURQUOI CE FICHIER EXISTE
# --------------------------
# Avant, chaque cible était un volume Docker nommé, rempli par le `COPY --from=build
# /app/dist /dist` de l'image. Or Docker n'initialise un volume nommé depuis l'image
# QUE s'il est vide : une fois rempli, tout nouveau build était ignoré. Le seul moyen
# de livrer était donc de supprimer le volume, ce qui exige qu'aucun conteneur ne
# l'utilise, donc d'arrêter nginx. D'où 1 min 30 de coupure totale à chaque
# déploiement.
#
# Ici on sort le statique des images à la main, dans une release datée sur l'hôte,
# et on bascule un lien symbolique. nginx ne s'arrête jamais.
#
#   /srv/monumia/app/
#   ├── releases/
#   │   ├── 5511cec/
#   │   └── a3f91b2/
#   └── current -> releases/a3f91b2
#
# nginx monte /srv/monumia/app en lecture seule et sert `current/`. Le lien est
# RELATIF pour se résoudre aussi bien sur l'hôte que dans le conteneur.

RELEASE_ROOT="/srv/monumia"

# publish_dist <cible> <image> <sha>
#
# Extrait /dist de l'image dans releases/<sha>, puis bascule `current` dessus.
# La bascule est atomique : un rename ne peut pas laisser nginx voir un état
# intermédiaire. Si le build est vide, on refuse de basculer et on garde la
# release précédente en ligne.
publish_dist() {
  local target="$1" image="$2" sha="$3"
  local base="$RELEASE_ROOT/$target"
  local rel="releases/$sha"
  local dest="$base/$rel"

  sudo mkdir -p "$base/releases"

  # Rebuild du même sha (re-déploiement) : on repart d'un répertoire propre pour
  # ne pas laisser traîner les fichiers d'un build précédent.
  sudo rm -rf "$dest"
  sudo mkdir -p "$dest"

  local cid
  cid=$(sudo docker create "$image")
  sudo docker cp "$cid:/dist/." "$dest/"
  sudo docker rm -v "$cid" >/dev/null

  if [ ! -f "$dest/index.html" ]; then
    echo "❌ $target : build vide, index.html absent de $dest. Bascule annulée,"
    echo "   la release précédente reste en ligne."
    sudo rm -rf "$dest"
    return 1
  fi

  # `ln -sfn` seul n'est pas atomique quand la cible existe déjà (unlink puis
  # symlink : fenêtre où `current` n'existe pas). On passe par un temporaire
  # renommé par-dessus.
  #
  # Le `-T` de mv est OBLIGATOIRE, pas cosmétique : sans lui, `current` étant un
  # lien vers un répertoire, mv déplace le temporaire À L'INTÉRIEUR de ce
  # répertoire au lieu de remplacer le lien. La bascule échoue alors en silence
  # et l'ancienne version reste servie. C'est du GNU coreutils, donc absent de
  # macOS : ce script est prévu pour tourner sur le VPS Linux.
  sudo ln -sfn "$rel" "$base/.current.tmp"
  sudo mv -T "$base/.current.tmp" "$base/current"

  echo "   $target → $sha"
}

# prune_releases <cible> [n_à_garder]
#
# Garde les n releases les plus récentes, plus celle actuellement en ligne (au
# cas où un rollback l'aurait fait sortir des n plus récentes).
prune_releases() {
  local target="$1" keep="${2:-3}"
  local base="$RELEASE_ROOT/$target"
  local dir="$base/releases"
  [ -d "$dir" ] || return 0

  local current=""
  if [ -L "$base/current" ]; then
    current=$(basename "$(readlink "$base/current")")
  fi

  local old
  while IFS= read -r old; do
    [ -z "$old" ] && continue
    [ "$old" = "$current" ] && continue
    sudo rm -rf "${dir:?}/$old"
  done < <(sudo ls -1t "$dir" 2>/dev/null | tail -n +$((keep + 1)))
}

# reload_nginx
#
# Rechargement gracieux : nginx démarre de nouveaux workers et laisse les anciens
# terminer les requêtes en cours. Aucune connexion perdue, contrairement à un
# stop/start.
#
# Ce n'est PAS ce qui rend la nouvelle version visible : nginx résout `current`
# à chaque requête, la bascule est donc prise en compte immédiatement (vérifié :
# 300 requêtes pendant deux bascules, aucune erreur, contenu à jour sans reload).
# Le reload sert à recharger nginx.conf lui-même quand il a changé.
#
# Retourne non zéro si la config est invalide, pour que l'appelant le signale.
# nginx continue alors de tourner avec sa config précédente.
#
# LE PIÈGE DU MONTAGE D'UN FICHIER SEUL
# docker-compose.yml monte `nginx/nginx.conf` comme un fichier, pas comme un
# dossier : Docker lie alors l'INODE, pas le chemin. `git pull` remplace le
# fichier par un nouveau (nouvel inode), et le conteneur continue de voir
# l'ancien jusqu'à sa recréation. Un `nginx -t` puis un reload relisaient donc
# la vieille config, en annonçant un succès. Vu le 2026-10-03 : les en-têtes de
# cache du 2026-08-26 n'avaient jamais atteint la prod, le conteneur datait du
# 2026-08-02.
#
# D'où deux temps : la config de l'HÔTE est testée dans le conteneur (copiée à
# part, incluse par un nginx.conf de test), puis, si le conteneur voit un autre
# fichier que l'hôte, il est recréé (1 à 2 s de coupure, seulement quand
# nginx.conf a changé). Sinon, simple reload sans coupure.
NGINX_CONF_HOTE="nginx/nginx.conf"
NGINX_CONF_CONTENEUR="/etc/nginx/conf.d/default.conf"

reload_nginx() {
  local test_conf='/tmp/nginx-test.conf'
  sudo docker cp "$NGINX_CONF_HOTE" monumia-nginx:/tmp/default.conf
  # Le nginx.conf principal de l'image inclut conf.d/*.conf : on le réécrit pour
  # inclure la copie. Si l'image change de structure et que la substitution
  # échoue, on refuse plutôt que de tester l'ancien fichier sans le savoir.
  if ! sudo docker exec monumia-nginx sh -c \
      "sed 's#/etc/nginx/conf.d/\*.conf#/tmp/default.conf#' /etc/nginx/nginx.conf > $test_conf \
       && grep -q '/tmp/default.conf' $test_conf \
       && nginx -t -q -c $test_conf" >/dev/null 2>&1; then
    echo "❌ config nginx invalide, rechargement refusé :"
    sudo docker exec monumia-nginx nginx -t -c "$test_conf" 2>&1 | sed 's/^/     /' || true
    return 1
  fi

  local empreinte_hote empreinte_conteneur
  empreinte_hote=$(md5sum < "$NGINX_CONF_HOTE" | cut -d' ' -f1)
  empreinte_conteneur=$(sudo docker exec monumia-nginx md5sum "$NGINX_CONF_CONTENEUR" | cut -d' ' -f1)

  if [ "$empreinte_hote" = "$empreinte_conteneur" ]; then
    sudo docker exec monumia-nginx nginx -s reload
    echo "   nginx rechargé"
    return 0
  fi

  echo "   nginx voit une ancienne version de nginx.conf (montage d'un fichier seul) :"
  echo "   recréation du conteneur"
  # --no-deps : sans lui, --force-recreate recréerait aussi les backends dont
  # nginx dépend (depends_on), avec leurs secondes de 502.
  sudo docker compose up -d --no-deps --force-recreate nginx
  empreinte_conteneur=$(sudo docker exec monumia-nginx md5sum "$NGINX_CONF_CONTENEUR" | cut -d' ' -f1)
  if [ "$empreinte_hote" != "$empreinte_conteneur" ]; then
    echo "❌ nginx recréé mais voit toujours une autre config que l'hôte"
    return 1
  fi
  echo "   nginx recréé avec la config à jour"
}
