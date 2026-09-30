# shellcheck shell=bash
#
# Étapes de déploiement qu'on ne refait que si leur entrée a bougé.
# Partagé par deploy.sh (beta + prod) et beta.sh (beta seule).
#
# EMPREINTES
# ----------
# Chaque étape a une empreinte : le hash des blobs git des fichiers dont elle
# dépend. Après un succès, l'empreinte est notée dans .deploy-state/<étape>. Au
# déploiement suivant, même empreinte = rien à refaire.
#
# On ne compare PAS à la release précédente (`git diff avant..après`) : un
# déploiement qui échoue après le `git pull` ferait croire au suivant que tout
# est déjà à jour. Ici, seule une étape réussie est notée, par environnement.
#
#   FORCE=1 ./deploy.sh    refait tout sans regarder les empreintes (après une
#                          base restaurée, une ligne d'aide éditée à la main…)
#
# Le répertoire .deploy-state/ est ignoré par git ; le supprimer revient à
# FORCE=1 pour le déploiement suivant.

ETAT_DIR=".deploy-state"

# empreinte <pathspec...>
#
# Lit l'index, qui vaut HEAD juste après le `git pull`. `git ls-files` plutôt
# que `ls-tree` pour avoir la magie des pathspecs (`:(exclude)`, `:(glob)`).
empreinte() {
  git ls-files -s -- "$@" | sha1sum | cut -c1-40
}

# etape_a_jour <étape> <empreinte> : vrai si l'étape a déjà réussi sur cette
# empreinte (et que FORCE n'est pas posé).
etape_a_jour() {
  [ -z "${FORCE:-}" ] || return 1
  [ -f "$ETAT_DIR/$1" ] && [ "$(cat "$ETAT_DIR/$1")" = "$2" ]
}

noter_etape() {
  mkdir -p "$ETAT_DIR"
  printf '%s\n' "$2" > "$ETAT_DIR/$1"
}

# Ce qui change le comportement d'un backend en marche : tout backend/, sauf ce
# que l'API ne lit jamais (preuves des sources, fiches de review, prospection,
# tests, scripts hors ligne). Un commit d'ingestion qui n'ajoute que des
# snapshots ne redémarre donc rien.
empreinte_backend() {
  empreinte backend \
    ':(exclude)backend/data/sources' \
    ':(exclude)backend/data/reviews' \
    ':(exclude)backend/data/prospection' \
    ':(exclude)backend/tests' \
    ':(exclude)backend/scripts'
}

# Ce que le sync YAML → aides_v3 lit : les fiches, les faits, les modules
# Python de la racine de backend/ (schéma, libellés, pièces) et le loader.
empreinte_aides() {
  empreinte backend/data/aides \
    ':(glob)backend/data/*.yaml' \
    ':(glob)backend/*.py' \
    backend/scripts/load_aides_yaml.py
}

# redemarrer_backends <service...>
#
# Le code Python vient du bind mount ./backend:/app, pas de l'image : `git pull`
# le met à jour sur disque, mais uvicorn (sans --reload) garde l'ancien en
# mémoire. Il faut donc redémarrer quand le code a changé. Quand il n'a pas
# changé, `up -d` seul ne recrée que si l'image, docker-compose.yml ou le .env
# ont bougé, et sinon ne coupe rien : pas de 502 pour un déploiement qui ne
# touche que le front.
redemarrer_backends() {
  local e
  e=$(empreinte_backend)

  local svc a_jour=1
  for svc in "$@"; do
    etape_a_jour "backend-$svc" "$e" || a_jour=0
  done

  if [ "$a_jour" -eq 1 ]; then
    echo "   code backend inchangé : pas de redémarrage forcé"
    sudo docker compose up -d --no-deps "$@"
  else
    sudo docker compose up -d --no-deps --force-recreate "$@"
  fi

  for svc in "$@"; do
    noter_etape "backend-$svc" "$e"
  done
}

# sync_aides <label> <conteneur>
#
# Sync YAML → aides_v3. Git est la source de vérité des aides ; le moteur
# déterministe les sert depuis les YAML (id = slug) mais la création de dossier
# (POST /api/dossiers) résout le slug dans aides_v3. Sans ce sync, toute aide
# ajoutée en YAML mais absente de aides_v3 renvoie « Aide introuvable » à la
# création. Idempotent (upsert par slug), donc sauté quand rien de ce qu'il lit
# n'a bougé depuis le dernier sync réussi de cet environnement.
sync_aides() {
  local label="$1" container="$2" e
  e=$(empreinte_aides)

  if etape_a_jour "aides-$label" "$e"; then
    echo "sync aides $label : YAML inchangés depuis le dernier sync, sauté"
    return 0
  fi

  if sudo docker exec "$container" python scripts/load_aides_yaml.py; then
    noter_etape "aides-$label" "$e"
    echo "sync aides $label : OK"
  else
    echo "sync aides $label : ÉCHEC"
    return 1
  fi
}

# prefixer <texte> : préfixe chaque ligne, pour démêler deux tâches lancées en
# parallèle dont les sorties s'entrelacent.
prefixer() {
  sed -u "s/^/   [$1] /"
}
