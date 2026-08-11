# Monumia — Guide dev

## Prérequis

- [Node.js](https://nodejs.org) (v20+)
- [Python 3.12+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Supabase CLI](https://supabase.com/docs/guides/cli/getting-started)

## Installation

```bash
git clone https://github.com/EpsilonFO/monumia
cd monumia
```

### 1. Dépendances backend + hooks git

```bash
./setup.sh
```

Installe les dépendances Python (dont les outils de dev) et configure les hooks pre-push.

### 2. Dépendances frontend

```bash
cd frontend && npm install
```

### 3. Variables d'environnement

**`backend/.env`**
```env
SUPABASE_URL=
SUPABASE_PUBLISHABLE_KEY=
SUPABASE_SECRET_KEY=
SUPABASE_SERVICE_KEY=
RESEND_API_KEY=
RESEND_FROM="Monumia <invitations@monumia.fr>"
# Uniquement pour les outils hors ligne (/ingest-aide, veille des aides).
# Le diagnostic servi au produit est déterministe et n'appelle aucun LLM.
DEEPSEEK_API_KEY=
```

**Emails d'invitation (projets partagés).** Si `RESEND_API_KEY` est vide, les emails d'invitation sont écrits dans la console (mode dev) — pratique pour développer sans compte Resend. Pour envoyer en réel : créer un compte [Resend](https://resend.com), vérifier le domaine `monumia.fr` (enregistrements DNS SPF/DKIM/DMARC), générer une clé API, et renseigner `RESEND_API_KEY` (et éventuellement `RESEND_FROM`).

**`frontend/.env`**
```env
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
```

Demande les valeurs à un autre dev.

## Base de données locale

```bash
supabase start       # démarre Supabase en local sur http://127.0.0.1:54321
supabase db reset    # applique toutes les migrations
supabase stop        # arrête Supabase
```

Les fichiers `backend/.env.local` et `frontend/.env.local` contiennent déjà les clés Supabase locales — ils sont chargés automatiquement en priorité sur `.env`.

## Lancer l'application

```bash
# Terminal 1 — backend
cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — frontend
cd frontend && npm run dev
```

- Backend : http://localhost:8000
- Frontend : http://localhost:3000

## Hooks pre-push

À chaque `git push`, ces vérifications s'exécutent automatiquement :

| Hook | Ce qu'il vérifie |
|------|-----------------|
| `ruff format` | Formatage Python |
| `ruff check` | Lint Python |
| `pyright` | Types Python |
| `tsc` | Types TypeScript |

Si un hook échoue, le push est bloqué. Corrige l'erreur et relance.

Pour lancer les checks manuellement depuis la racine :

```bash
# Python
uv run --project backend ruff format backend/
uv run --project backend ruff check backend/
uv run --project backend pyright backend/

# TypeScript
cd frontend && npx tsc --noEmit
```
