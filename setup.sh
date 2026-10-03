#!/bin/sh
set -e

echo "Installing backend dependencies..."
cd backend && uv sync --group dev && cd ..

# Le groupe `pipeline` tire `providall` depuis un dépôt privé en SSH : il n'est
# nécessaire qu'à `scripts/` (prospection, ingestion) et à leurs tests, pas à
# l'API. On l'ajoute sans faire échouer l'installation pour qui n'a pas l'accès.
echo "Installing ingestion pipeline dependencies (private repo, optional)..."
if ! (cd backend && uv sync --group dev --group pipeline); then
  echo "  providall inaccessible (dépôt privé EpsilonFO/providall) : le backend"
  echo "  fonctionne, mais scripts/ingerer.py, scripts/prospecter.py et leurs"
  echo "  tests ne tourneront pas. Relancer après avoir obtenu l'accès SSH :"
  echo "      cd backend && uv sync --group dev --group pipeline"
fi

echo "Installing pre-commit hooks..."
uv run --directory backend pre-commit install --hook-type pre-commit --hook-type pre-push

echo "Done. Git hooks are set up — gitleaks/ruff/tsc run on commit, pyright on push."
