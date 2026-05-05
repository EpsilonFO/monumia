#!/bin/sh
set -e

echo "Installing backend dependencies..."
cd backend && uv sync --group dev && cd ..

echo "Installing pre-commit hooks..."
uv run --directory backend pre-commit install --hook-type pre-commit --hook-type pre-push

echo "Done. Git hooks are set up — gitleaks/ruff/tsc run on commit, pyright on push."
