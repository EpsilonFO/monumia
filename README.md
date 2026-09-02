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

L'accès aux aides est payant (Stripe) et caviardé côté backend pour un compte sans
droits. Sans configurer Stripe, ouvrir l'accès à la main :

```bash
docker exec supabase_db_monumia psql -U postgres \
  -c "update public.users set has_aides_access = true;"
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

**Emails.** Sans `RESEND_API_KEY`, les emails (partage de projet, rappels d'aides)
sont écrits dans la console — suffisant pour développer. Pour envoyer en réel :
compte [Resend](https://resend.com), domaine `monumia.fr` vérifié
(SPF/DKIM/DMARC), puis `RESEND_API_KEY`, `RESEND_FROM` (invitations) et
`RESEND_FROM_RAPPELS` (rappels automatiques, expéditeur distinct pour qu'un
filtrage ou un désabonnement ne touche pas les invitations nominatives).

**Rappels d'aides.** [scripts/cron-rappels.sh](scripts/cron-rappels.sh) lance
chaque matin `backend/scripts/rappels_aides.py` dans le conteneur backend :
échéances de dépôt qui approchent (paliers réglables par utilisateur, 30 jours
par défaut) et guichets dont la date d'ouverture vient d'être franchie. Le cron
s'installe dans la crontab de root, comme la sauvegarde :

```
0 9 * * * /home/<user>/monumia/scripts/cron-rappels.sh >> /var/log/monumia-rappels.log 2>&1
```

Pour voir ce qui partirait sans rien envoyer :
`./scripts/cron-rappels.sh prod --dry-run`.

**Tester un rappel sans attendre le bon jour.** `--today` fige la date pour le
moteur aussi, donc le rejeu est fidèle : la fenêtre de candidature de chaque
aide est recalculée à cette date. Reste à savoir QUELLE date déclenche quoi,
d'où `--agenda` :

```bash
cd backend
uv run python scripts/rappels_aides.py --agenda --user <uuid>
#   --today 2027-04-15  échéance   merimee-prix-…  limite 2027-05-15 (J-30)
#   --today 2027-04-15  ouverture  merimee-prix-…  ouvre le 2027-04-15

# puis, en reprenant une de ces dates :
uv run python scripts/rappels_aides.py --today 2027-04-15 --user <uuid> --preview /tmp/apercus
```

`--agenda` simule (il rejoue le diagnostic à chaque date candidate) et couvre
400 jours de part et d'autre : une date passée se rejoue aussi bien qu'une date
future. `--preview` écrit les emails rendus en HTML, à ouvrir dans un
navigateur, et implique `--dry-run` — rien n'est envoyé, rien n'est journalisé.

Deux points pour un test en local : `APP_URL=http://localhost:3000` dans
`backend/.env.local`, sinon les liens des emails pointent vers la production ;
et le journal `aide_rappels_envoyes` doit exister, donc la migration doit être
appliquée. Pour rejouer un rappel déjà parti, vider sa ligne :

```sql
delete from aide_rappels_envoyes where user_id = '<uuid>';
```

**Clés LLM.** Le diagnostic servi au produit est déterministe et n'appelle aucun
LLM. `DEEPSEEK_API_KEY` et compagnie ne servent qu'aux outils hors ligne
(ingestion d'aides, veille des sources).

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
