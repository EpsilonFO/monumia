# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Le code, les commentaires et les échanges se font en français dans ce dépôt.

## Interdits absolus

Ces actions appartiennent à l'utilisateur, **jamais** à Claude :

- **`supabase db reset` : JAMAIS**, sous aucun prétexte, y compris en local — la commande détruit toutes les données de la base. Aucune situation ne justifie que Claude la lance ; s'il faut repartir d'un schéma propre, c'est l'utilisateur qui décide et qui exécute.
- **Migrations** : ne jamais lancer `supabase db push`, `supabase migration up`, ni `deploy.sh`/`beta.sh` (qui poussent les migrations). Écrire une migration est permis, l'appliquer non.
  - Créer le fichier **obligatoirement** avec `supabase migration new <nom>`, jamais avec `touch` ni en écrivant directement dans `supabase/migrations/` : le CLI horodate le nom au format attendu, un fichier créé à la main casse l'ordre d'application. Écrire le SQL dans le fichier rendu par la commande.
- **Git** : ne jamais lancer `git commit`, `git add`, `git rm` (ni `git push`, `git reset`, `git checkout` destructif). Modifier les fichiers du working tree est le travail attendu ; les mettre à l'index ou les committer revient à l'utilisateur.

Dans les deux cas : préparer le changement, puis dire à l'utilisateur quelle commande lancer.

## Commandes

Backend (toujours depuis `backend/`, via `uv`) :

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
uv run pytest -q                              # toute la suite
uv run pytest tests/test_eligibility_engine.py -q
uv run pytest tests/test_veille_apply.py::test_nom -q
uv run ruff format . && uv run ruff check --fix .
uv run pyright .
```

Frontend (depuis `frontend/`) :

```bash
npm run dev                 # http://localhost:3000
npm run test                # vitest run
npx vitest run src/lib/__tests__/qcm.test.ts
npx tsc -b                  # PAS `tsc --noEmit` : la racine tsconfig.json n'a que des
                            # références de projets, `--noEmit` ne vérifie rien
npm run lint
```

Base locale : `supabase start` / `supabase stop` (jamais `db reset`, cf. « Interdits absolus »). Les `.env.local` (backend et frontend) sont chargés en priorité sur `.env`.

CI (GitHub Actions) : ruff check + format check, pyright, pytest côté backend ; `npx tsc -b` + vitest côté frontend ; `npx tsc -b` côté landing. Les hooks pre-commit lancent `ruff format`/`ruff check --fix` suivis de `git add -u`, plus `scripts/tsc-check.sh` (qui type-check frontend **et** landing) ; les hooks pre-push relancent tout en mode vérification seule.

Détails d'installation, variables d'environnement et déploiement : [README.md](README.md), [docs/PROJET.md](docs/PROJET.md), [deploy.sh](deploy.sh).

## Ce que fait le produit

Monumia (ex-Patrys) identifie les aides au financement de la restauration du patrimoine (DRAC, Fondation du Patrimoine, régions, dispositifs fiscaux…) auxquelles un monument est éligible, puis accompagne le montage des dossiers. **Aucune notion de segment utilisateur.** Un compte est un compte : ni `commune`, ni `prive`, ni `btp`. Ce qui pilote l'éligibilité est `monuments.proprietaire` (10 valeurs, par projet), et les critères propres au propriétaire vivent dans les faits `scope: proprietaire` de `data/facts.yaml`. Ne pas réintroduire d'attribut de segment sur `users` : il avait été branché sur le filtrage des aides, retiré une fois (migration `20260516180000`), puis supprimé entièrement.

Vocabulaire : côté produit un **projet** est un **monument** (table `monuments`, routes `/app/projets/...`). Les alias `MONUMENTS`/`AIDES`/`DOSSIERS` dans [frontend/src/constants/routes.ts](frontend/src/constants/routes.ts) résolvent tous sur l'onglet Projet unifié — vestiges de migration.

## Architecture

```
frontend/   SPA React 19 + Vite + TS + Tailwind 4 + shadcn/ui + Zustand   → app.monumia.fr
landing/    site vitrine statique React                                    → monumia.fr
backend/    FastAPI (Python 3.12, uv) + Uvicorn                            → /api
supabase/   migrations PostgreSQL (Auth JWT, Storage bucket `documents`)
nginx/      reverse proxy + Certbot ; docker-compose gère prod + beta
```

Backend : [main.py](backend/main.py) monte 15 routers ([backend/routers/](backend/routers/)), [db.py](backend/db.py) expose les clients Supabase (service-role en singleton, anon par requête pour l'auth) et vérifie les JWT localement via JWKS, [config.py](backend/config.py) tient `ALLOWED_ORIGINS` — une seule liste sert à la fois au CORS et aux redirections de retour Stripe.

Frontend : un store Zustand et un service par domaine (`src/stores/`, `src/services/`), types dans `src/types/`, logique métier pure testable dans `src/lib/`.

## Le pipeline de diagnostic

C'est le point le plus important à comprendre avant de toucher au matching.

Un seul moteur, déterministe : `POST /aides/diagnostic-deterministe` → [eligibility_engine.py](backend/eligibility_engine.py). Il lit les YAML `backend/data/aides/*.yaml` (id = **slug**), ne fait **aucun appel réseau** (~2 ms/monument, YAML en cache) et ne persiste **rien** : le QCM se résout côté client via `eliminationsParOption`. Le front passe partout par `runProjectDiagnostic()` (wizard, page projet, liste, dashboard).

Le moteur ne traite que les aides **engine-ready** (zéro condition `kind: untyped`) ; les autres sont simplement ignorées.

Un pipeline LLM a existé (`POST /aides/diagnostic`, `matching_engine.py`, prompts Jinja2, table `diagnostics`, RPC `prefiltrer_aides`, appels DeepSeek). Il a été **entièrement supprimé** — code, tables et fonctions SQL. Ne pas le ressusciter : les conditions se typent en amont dans les YAML, pas au runtime.

Le champ `llmEvaluation` de la réponse est un **nom vestigial** : il porte les verdicts déterministes par condition, et cinq points du front le lisent sous ce nom. Ne pas le renommer à la légère.

Principe de fail-closed : une valeur inconnue rend `None` et produit une **incertitude** (aide « potentiellement éligible » + question), jamais une élimination. `evaluate_predicate` dans [aides_schema.py](backend/aides_schema.py) est le cœur de cette sémantique.

Les clés du dict `answers` préfixées par `_` (ex. `_raisons`) sont des métadonnées front, pas des faits — `split_reserved_answers()` les sépare avant `build_context`.

## Les données d'aides : `backend/data/`

**Le dossier `data/` est la source de vérité, pas Supabase.** Une aide modifiée directement en base sera écrasée par le loader. Lire [backend/data/README.md](backend/data/README.md) et [backend/data/TYPING.md](backend/data/TYPING.md) avant toute intervention.

```
data/facts.yaml         ontologie des faits (questions canoniques typées)
data/facts_pending.yaml faits proposés, en attente de validation humaine
data/aides/<slug>.yaml  une aide par fichier
data/sources/<slug>/    snapshots datés des pages officielles (preuve des quotes)
data/reviews/           fiches de review humaines
```

Workflow : éditer le YAML → `uv run python scripts/lint_aides_data.py` (exit 1 si erreur) → commit (**le diff git EST la revue**) → `uv run python scripts/load_aides_yaml.py` (upsert par slug). Claude s'arrête après le lint : le commit et le load sont des actions de l'utilisateur (cf. « Interdits absolus »).

Règles non négociables :
- `text` d'une condition n'est jamais reformulé — il vient de la source. Scinder une puce composite est permis, réécrire non.
- Une `quote` doit se retrouver littéralement dans le snapshot ; jamais de citation inventée.
- Un nouveau fait se propose dans `facts_pending.yaml`, jamais directement dans `facts.yaml`. Aucune question n'est générée au runtime.
- Les seeds `backend/scripts/seeds/seed_aide_*.py` sont **obsolètes** — ne plus les exécuter.

Trois skills couvrent ces tâches : `/ingest-aide` (ingestion/ré-extraction depuis les sources, avec vérification adversariale), `/typer-aides` (résorption des conditions `untyped`), et `scripts/veille_aides.py` (détection et application des changements de source, mandat volontairement étroit : jamais `kind`/`effect`/`fact`/`field`).

## Pièges connus

- **pyright n'analyse pas tout** : `pyproject.toml` exclut `scripts` et `routers`, et n'inclut que `*.py` racine + `services`. Une erreur de type dans un router ne sera vue ni en local ni en CI.
- **Deux espaces d'identifiants d'aides** cohabitent : slug (YAML, moteur déterministe) et UUID (`aides_v3`). `GET /aides/{id}` résout dans cet ordre UUID puis slug. La création de dossier passe par `aides_v3`, d'où l'étape de sync YAML → base à la fin de `deploy.sh` : une aide en YAML mais absente de `aides_v3` renvoie « Aide introuvable » à la création de dossier.
- **`vitest.config.ts` utilise `environment: 'node'`** : un test de composant React a besoin d'un environnement DOM explicite.
- L'accès aux aides est payant (Stripe) : `redact_diagnostic_if_locked` caviarde les résultats côté backend et `has_aides_access` / `src/lib/aides-access.ts` gouvernent l'affichage. Toute nouvelle route exposant des aides doit passer par ce filtre.
- Les accès aux monuments partagés passent par `require_project_access(supabase, monument_id, user_id, role)` — un filtre `user_id` renverrait 404 aux collaborateurs.
- Sans `RESEND_API_KEY`, les emails d'invitation sont écrits en console (mode dev).
