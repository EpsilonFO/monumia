#!/usr/bin/env bash
# Lance le serveur MCP Postgres en lecture seule sur la base prod ou beta.
#
#   scripts/mcp/lancer.sh prod|beta
#
# La chaîne de connexion vient du trousseau macOS (service monumia-mcp-<env>),
# jamais d'un fichier : ni le dépôt ni ~/.claude.json ne portent le mot de passe.
# Mise en place : scripts/mcp/README.md.
set -euo pipefail

case "${1:-}" in
  prod | beta) env="$1" ;;
  *)
    echo "usage : $0 prod|beta" >&2
    exit 2
    ;;
esac

service="monumia-mcp-$env"
if ! uri=$(security find-generic-password -s "$service" -w 2>/dev/null); then
  echo "Aucune entrée « $service » dans le trousseau (cf. scripts/mcp/README.md)." >&2
  exit 1
fi

# Filet contre une chaîne collée par erreur avec l'utilisateur postgres : le
# serveur ne part qu'avec le rôle sans droit d'écriture. Le pooler Supabase
# attend « mcp_lecture.<project_ref> », la connexion directe « mcp_lecture ».
case "$uri" in
  postgres://mcp_lecture[.:@]* | postgresql://mcp_lecture[.:@]*) ;;
  *)
    echo "Refus : la chaîne « $service » ne se connecte pas en mcp_lecture." >&2
    exit 1
    ;;
esac

if ! command -v uvx >/dev/null; then
  echo "uvx introuvable dans le PATH." >&2
  exit 1
fi

export DATABASE_URI="$uri"

# Version figée : un serveur qui voit la prod ne se met pas à jour tout seul.
# postgres-mcp 0.3.0 ne borne pas sa dépendance mcp, et mcp 2.x a renommé
# FastMCP : sans « mcp<2 », le serveur ne démarre pas.
exec uvx --quiet --with 'mcp<2' postgres-mcp@0.3.0 --access-mode=restricted
