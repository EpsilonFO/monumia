# Monumia — Guide dev

Monumia identifie les aides au financement de la restauration du patrimoine (DRAC,
Fondation du Patrimoine, régions, dispositifs fiscaux…) auxquelles un monument est
éligible, puis accompagne le montage des dossiers.

- Architecture, pipeline de diagnostic, conventions : [CLAUDE.md](CLAUDE.md)
- Fonctionnement produit et déploiement : [docs/PROJET.md](docs/PROJET.md)

## Prérequis

- [Docker](https://docs.docker.com/get-docker/) — la stack Supabase locale tourne dedans
- [Node.js](https://nodejs.org) 20+
- [Python](https://www.python.org/downloads/) 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Supabase CLI](https://supabase.com/docs/guides/cli/getting-started) 2.84+

## Installation

Les cinq étapes ci-dessous partent d'un dépôt fraîchement cloné et se terminent sur
une application fonctionnelle, avec sa base peuplée.

### 1. Cloner et installer les dépendances

```bash
git clone https://github.com/EpsilonFO/monumia
cd monumia

./setup.sh                      # dépendances Python + hooks git (pre-commit, pre-push)
cd frontend && npm install && cd ..
cd landing && npm install && cd ..    # optionnel : site vitrine
```

### 2. Base locale et variables d'environnement

```bash
./scripts/setup-env-local.sh
```

Ce script démarre la stack Supabase locale si besoin (`supabase start`, qui applique
au passage toutes les migrations de [supabase/migrations/](supabase/migrations/)),
puis génère `backend/.env.local` et `frontend/.env.local` à partir des clés que le
CLI vient de créer. Ces deux fichiers sont gitignorés, propres à chaque machine, et
chargés en priorité sur `.env` : il n'y a aucune clé à se faire passer entre
développeurs pour travailler en local.

Le premier démarrage télécharge les images Docker — comptez plusieurs minutes.

Après un `supabase stop && supabase start`, les clés peuvent changer :
`./scripts/setup-env-local.sh --force` réécrit les deux fichiers.

### 3. Peupler la base

Les migrations créent le schéma, pas les données. Sans cette étape, la recherche de
monuments ne renvoie rien et aucun dossier ne peut être créé.

```bash
cd backend

uv run python scripts/seeds/seed_all.py     # référentiels : communes, EPCI, Mérimée
uv run python scripts/load_aides_yaml.py    # les ~140 aides de data/aides/*.yaml
uv run python scripts/seed_templates.py     # modèles de documents (optionnel)
```

[seed_all.py](backend/scripts/seeds/seed_all.py) enchaîne les quatre scripts de
peuplement dans l'ordre où leurs dépendances l'exigent, lit tout seul l'URL et la
clé d'écriture dans `supabase status`, et supprime les CSV téléchargés (COG INSEE,
Mérimée) une fois terminé. Compter une dizaine de minutes : ~35 000 communes et
~47 000 monuments à insérer, sources à télécharger comprises.

`load_aides_yaml.py` fait l'upsert par slug de `backend/data/aides/*.yaml` vers la
table `aides_v3`. C'est cette table que consulte la création de dossier — une aide
présente en YAML mais absente de la base renvoie « Aide introuvable ».

### 4. Lancer l'application

Deux terminaux :

```bash
# Terminal 1 — backend
cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — frontend
cd frontend && npm run dev
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Supabase Studio | http://127.0.0.1:54323 |
| Emails de dev (Mailpit) | http://127.0.0.1:54324 |
| Site vitrine (`cd landing && npm run dev`) | http://localhost:3001 |

`/docs` n'est exposé que parce que `ENV=development` figure dans le `.env.local`
généré ; en production il est désactivé.

### 5. Créer un compte et débloquer les aides

L'inscription depuis http://localhost:3000 fonctionne immédiatement : la
confirmation par email est désactivée en local
([supabase/config.toml](supabase/config.toml), `enable_confirmations = false`).

Le détail des aides est gratuit. Ce qui se paie, ce sont les volumes (monuments,
projets), le calendrier (échéancier, aides à venir) et la veille par email : deux
abonnements, `veille` et `multi_monuments`, tous deux négociés (aucun montant
affiché, la page Tarifs renvoie vers `contact@monumia.fr`). Stripe ne sert donc
qu'à facturer une offre convenue. Pour ouvrir une offre à la main sur un compte
local :

```bash
docker exec supabase_db_monumia psql -U postgres -c "
  insert into public.subscriptions (stripe_subscription_id, user_id, stripe_customer_id, plan, status)
  select 'sub_local', id, 'cus_local', 'multi_monuments', 'active' from public.users limit 1;"
```

## Au quotidien

```bash
supabase start / supabase stop        # base locale
```

⚠️ `supabase db reset` détruit toutes les données locales, y compris les
référentiels de l'étape 3 (une dizaine de minutes à re-télécharger). Les migrations
sont appliquées par `supabase start` sur une base vierge.

```bash
# Backend (depuis backend/)
uv run pytest -q
uv run ruff format . && uv run ruff check --fix .
uv run pyright .

# Frontend (depuis frontend/)
npm run test
npx tsc -b          # PAS `tsc --noEmit` : la racine n'a que des références de projets
npm run lint
```

## Variables d'environnement

| Fichier | Rôle | Modèle |
|---------|------|--------|
| `backend/.env.local` | dev local, généré par `scripts/setup-env-local.sh` | — |
| `frontend/.env.local` | dev local, généré par `scripts/setup-env-local.sh` | — |
| `backend/.env` | déploiement du backend, ou pointer une Supabase distante | [backend/.env.example](backend/.env.example) |
| `frontend/.env` | build de la SPA | [frontend/.env.example](frontend/.env.example) |
| `landing/.env` | build du site vitrine | [landing/.env.example](landing/.env.example) |
| `.env` (racine) | build args de `docker-compose.yml` (prod + beta) | [.env.example](.env.example) |

Les `.env.local` sont chargés en priorité sur les `.env`, côté backend
([db.py](backend/db.py)) comme côté Vite.

**Emails d'invitation.** Sans `RESEND_API_KEY`, les emails de partage de projet sont
écrits dans la console — suffisant pour développer. Pour envoyer en réel : compte
[Resend](https://resend.com), domaine `monumia.fr` vérifié (SPF/DKIM/DMARC), puis
`RESEND_API_KEY` et `RESEND_FROM`.

**Clés LLM.** Le diagnostic servi au produit est déterministe et n'appelle aucun
LLM. `DEEPSEEK_API_KEY` et compagnie ne servent qu'aux outils hors ligne
(ingestion d'aides, veille des sources).

**Administration du catalogue.** `ADMIN_USER_IDS` liste les UUID Supabase des
comptes qui ouvrent la page `/admin` (retirer une aide du catalogue, reformuler
une question du questionnaire), séparés par des virgules. À renseigner **par
environnement** — prod et beta ont chacun leur projet Supabase, donc des
identifiants différents pour les mêmes personnes — puis à redémarrer le backend.
Vide ou absente : aucun administrateur, et les sept routes `/admin/...`
répondent 403.

## Hooks git

Installés par `./setup.sh`.

| Moment | Ce qui tourne |
|--------|---------------|
| pre-commit | gitleaks, `ruff format`, `ruff check --fix`, `tsc -b` |
| pre-push | les mêmes en vérification seule, plus `pyright` |

Si un hook échoue, l'opération est bloquée. Les mêmes vérifications tournent en CI
(GitHub Actions).

Pour les lancer à la main depuis la racine :

```bash
uv run --project backend ruff format --check backend/
uv run --project backend ruff check backend/
uv run --project backend pyright backend/
cd frontend && npx tsc -b && npm run test
```
