# PatriAlta

Application de gestion des aides à la rénovation du patrimoine.

---

## Lancement rapide (Mac)

### Étape 1 — Télécharger le projet

Si tu n'as pas encore le projet sur ton ordinateur, ouvre le **Terminal** (cherche "Terminal" dans Spotlight avec `Cmd + Espace`) et tape :

```
git clone https://github.com/EpsilonFO/patrialta
cd patrialta
```

> Si git n'est pas installé, Mac te proposera de l'installer automatiquement.

---

### Étape 2 — Rendre le script exécutable (une seule fois)

Dans le Terminal, depuis le dossier `patrialta` :

```
chmod +x start.sh
```

---

### Étape 3 — Lancer l'application

```
./start.sh
```

Le script va automatiquement :
- Vérifier et installer Node.js si nécessaire
- Vérifier et installer Python si nécessaire
- Installer toutes les dépendances
- Démarrer le backend et le frontend
- Ouvrir l'application dans ton navigateur

L'application s'ouvre sur **http://localhost:3000**

Pour arrêter l'application : appuie sur `Ctrl + C` dans le Terminal.

---

## En cas de problème

### "Permission refusée" au lancement

```
chmod +x start.sh
./start.sh
```

### Le navigateur ne s'ouvre pas automatiquement

Ouvre manuellement http://localhost:3000 dans ton navigateur.

### Erreur au démarrage

Consulte les fichiers de log pour voir l'erreur détaillée :
- `logs/backend.log` — erreurs du serveur
- `logs/frontend.log` — erreurs de l'interface

### Homebrew manquant (Mac)

Si le script te demande d'installer Homebrew, colle cette commande dans le Terminal :

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Puis relance `./start.sh`.

---

## Structure du projet

```
patrialta/
├── backend/     → Serveur API (Python / FastAPI) — port 8000
├── frontend/    → Interface web (React) — port 3000
├── logs/        → Fichiers de log générés au démarrage
└── start.sh     → Script de démarrage
```

---

## Pour les développeurs

### Prérequis

- Node.js 18+
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (gestionnaire de paquets Python)

### Mise en place après le clone

**1. Installer les dépendances backend et les git hooks :**

```bash
./setup.sh
```

Ce script installe les dépendances Python (dont `ruff` et `pyright`) et configure un hook `pre-push` qui vérifie automatiquement le code avant chaque push.

**2. Installer les dépendances frontend :**

```bash
cd frontend && npm install
```

### CI

Un workflow GitHub Actions tourne sur chaque push (toutes branches). Il vérifie :
- `ruff format --check` — formatage Python
- `ruff check` — lint Python
- `pyright` — type checking Python

Si un check échoue, le push est signalé sur GitHub. Le hook `pre-push` installé via `setup.sh` fait tourner les mêmes vérifications localement avant d'envoyer.

Pour lancer les checks manuellement :

```bash
cd backend
uv run ruff format .       # formate les fichiers
uv run ruff check .        # lint
uv run pyright .           # type check
```

### Démarrage manuel

**Backend :**
```bash
cd backend
uv sync
uv run uvicorn main:app --reload --port 8000
```

**Frontend :**
```bash
cd frontend
npm install
npm run dev
```

### Avec Docker

```bash
docker compose up --build
```