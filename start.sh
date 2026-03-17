#!/bin/bash

# ============================================================
#  PatriAlta — Script de démarrage
# ============================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_step() { echo -e "\n${BLUE}▶ $1${NC}"; }
print_ok()   { echo -e "${GREEN}✓ $1${NC}"; }
print_warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
print_err()  { echo -e "${RED}✗ $1${NC}"; }

echo ""
echo -e "${BLUE}╔═══════════════════════════════════╗${NC}"
echo -e "${BLUE}║        PatriAlta — Démarrage      ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════╝${NC}"

# ── 1. Vérification de Node.js ─────────────────────────────
print_step "Vérification de Node.js..."
if ! command -v node &>/dev/null; then
  print_warn "Node.js non trouvé. Installation en cours..."
  if [[ "$OSTYPE" == "darwin"* ]]; then
    if command -v brew &>/dev/null; then
      brew install node
    else
      print_err "Homebrew requis pour installer Node.js sur Mac."
      echo "  → Installe Homebrew : https://brew.sh"
      echo "  → Puis relance ce script."
      exit 1
    fi
  else
    print_err "Node.js non trouvé. Installe-le depuis https://nodejs.org"
    exit 1
  fi
fi
NODE_VERSION=$(node --version)
print_ok "Node.js $NODE_VERSION"

# ── 2. Vérification de Python 3.12+ ───────────────────────
print_step "Vérification de Python..."
PYTHON_CMD=""
for cmd in python3.12 python3 python; do
  if command -v "$cmd" &>/dev/null; then
    VERSION=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
    MAJOR=$(echo "$VERSION" | cut -d. -f1)
    MINOR=$(echo "$VERSION" | cut -d. -f2)
    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 12 ]; then
      PYTHON_CMD="$cmd"
      break
    fi
  fi
done

if [ -z "$PYTHON_CMD" ]; then
  print_warn "Python 3.12+ non trouvé. Installation en cours..."
  if [[ "$OSTYPE" == "darwin"* ]] && command -v brew &>/dev/null; then
    brew install python@3.12
    PYTHON_CMD="python3.12"
  else
    print_err "Python 3.12+ requis. Installe-le depuis https://www.python.org/downloads/"
    exit 1
  fi
fi
print_ok "Python $($PYTHON_CMD --version)"

# ── 3. Vérification de uv (gestionnaire Python) ───────────
print_step "Vérification de uv..."
if ! command -v uv &>/dev/null; then
  print_warn "uv non trouvé. Installation en cours..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  if ! command -v uv &>/dev/null; then
    print_err "Impossible d'installer uv. Essaie manuellement : https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
  fi
fi
print_ok "uv $(uv --version)"

# ── 4. Vérification des fichiers .env ─────────────────────
print_step "Vérification de la configuration..."
if [ ! -f "backend/.env" ]; then
  print_err "Fichier backend/.env manquant."
  echo "  → Crée le fichier backend/.env avec les informations Supabase."
  echo "  → Voir README.md pour les détails."
  exit 1
fi
if [ ! -f "frontend/.env" ]; then
  print_err "Fichier frontend/.env manquant."
  echo "  → Crée le fichier frontend/.env avec les informations Supabase."
  echo "  → Voir README.md pour les détails."
  exit 1
fi
print_ok "Fichiers de configuration trouvés"

# ── 5. Installation des dépendances backend ───────────────
print_step "Installation des dépendances backend..."
cd backend
uv sync --quiet
cd ..
print_ok "Dépendances backend installées"

# ── 6. Installation des dépendances frontend ──────────────
print_step "Installation des dépendances frontend..."
cd frontend
npm install --silent
cd ..
print_ok "Dépendances frontend installées"

# ── 7. Démarrage des serveurs ─────────────────────────────
print_step "Démarrage de l'application..."
echo ""
echo -e "  ${GREEN}Backend  →${NC} http://localhost:8000"
echo -e "  ${GREEN}Frontend →${NC} http://localhost:3000"
echo ""
echo -e "  ${YELLOW}Pour arrêter : appuie sur Ctrl+C${NC}"
echo ""

# Fonction pour arrêter les deux serveurs proprement
cleanup() {
  echo ""
  print_warn "Arrêt de l'application..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
  wait $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
  echo -e "${GREEN}Application arrêtée.${NC}"
  exit 0
}
trap cleanup INT TERM

# Lancement backend
cd backend
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# Lancement frontend
cd frontend
npm run dev -- --port 3000 > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# Attendre que les serveurs démarrent
sleep 3

# Vérifier que les processus tournent
if ! kill -0 $BACKEND_PID 2>/dev/null; then
  print_err "Le backend n'a pas démarré. Consulte logs/backend.log pour les détails."
  exit 1
fi
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
  print_err "Le frontend n'a pas démarré. Consulte logs/frontend.log pour les détails."
  exit 1
fi

print_ok "Application démarrée !"
echo ""

# Ouvrir le navigateur automatiquement
if [[ "$OSTYPE" == "darwin"* ]]; then
  sleep 2
  open http://localhost:3000
fi

# Attendre que les processus se terminent
wait $BACKEND_PID $FRONTEND_PID