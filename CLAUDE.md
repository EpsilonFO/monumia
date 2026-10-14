# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Le code, les commentaires et les échanges se font en français dans ce dépôt.

## Interdits absolus

Ces actions appartiennent à l'utilisateur, **jamais** à Claude :

- **`supabase db reset` : JAMAIS**, sous aucun prétexte, y compris en local — la commande détruit toutes les données de la base. Aucune situation ne justifie que Claude la lance ; s'il faut repartir d'un schéma propre, c'est l'utilisateur qui décide et qui exécute.
- **Migrations** : ne jamais lancer `supabase db push`, `supabase migration up`, ni `deploy.sh`/`beta.sh` (qui poussent les migrations). Le lanceur de dev (`npm run monumia`, `monumia`) pousse lui aussi les migrations locales : Claude ne le lance qu'avec `--sans-db`. Écrire une migration est permis, l'appliquer non.
  - Créer le fichier **obligatoirement** avec `supabase migration new <nom>`, jamais avec `touch` ni en écrivant directement dans `supabase/migrations/` : le CLI horodate le nom au format attendu, un fichier créé à la main casse l'ordre d'application. Écrire le SQL dans le fichier rendu par la commande.
- **Git** : ne jamais lancer `git commit`, `git add`, `git rm` (ni `git push`, `git reset`, `git checkout` destructif). Modifier les fichiers du working tree est le travail attendu ; les mettre à l'index ou les committer revient à l'utilisateur.

Dans les deux cas : préparer le changement, puis dire à l'utilisateur quelle commande lancer.

## Commandes

Tout le dev local en une commande, depuis la racine du dépôt ou d'un worktree : `npm run monumia` ([scripts/dev/](scripts/dev/), Node sans dépendance). Il prépare le dépôt (git fetch, Supabase local, `.env` copiés du dépôt principal, migrations locales, `uv sync`, `npm ci` si le lockfile a changé, ports) puis ouvre un écran plein terminal avec backend, frontend et landing. `--sans-db` saute les migrations, `--prep` s'arrête après la préparation.

Backend (toujours depuis `backend/`, via `uv`) :

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
uv run pytest -q                              # toute la suite
uv run pytest tests/test_eligibility_engine.py -q
uv run pytest tests/test_veille_apply.py::test_nom -q
uv run ruff format . && uv run ruff check --fix .
uv run pyright .
```

Dans un **worktree neuf**, le venv se crée sans `providall` (groupe `pipeline`, non
installé par défaut parce qu'il vient d'un dépôt privé en SSH, cf. `pyproject.toml`) :
les tests du pipeline ne s'importent plus et pyright rate onze imports. Un
`uv sync --group dev --group pipeline` depuis `backend/` répare, et côté frontend il
faut un `npm ci` (ou le lien que pose `scripts/tsc-check.sh`).

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

Monumia (ex-Patrys) identifie les aides au financement de la restauration du patrimoine (DRAC, Fondation du Patrimoine, régions, dispositifs fiscaux…) auxquelles un monument est éligible, puis accompagne le montage des dossiers. **Aucune notion de segment utilisateur.** Un compte est un compte : ni `commune`, ni `prive`, ni `btp`. Ce qui pilote l'éligibilité est `monuments.proprietaire` (par monument), et les critères propres au propriétaire vivent dans les faits `scope: proprietaire` de `data/facts.yaml`.

`monuments.proprietaire` est un **choix multiple** (`ownership_type[]`, jamais vide, migration `20260930084241`) : un bien peut avoir plusieurs propriétaires, et une aide est proposée dès qu'**un seul** d'entre eux peut la déposer. Le moteur évalue donc chaque aide une fois par propriétaire coché (`profils_par_proprietaire`, contexte où le champ vaut ce seul code) et garde le meilleur verdict ; le questionnaire pose l'union des questions des profils encore ouverts, et une réponse n'élimine l'aide que si elle élimine tous ces profils. Les prédicats YAML restent écrits sur UNE valeur (`eq`/`in`/`neq`/`not_in`) et `FIELD_REGISTRY` garde le champ en `enum` : c'est l'évaluation par profil qui les rend justes, ne pas les réécrire en `contains`. Évaluer condition par condition « pour au moins un propriétaire » serait faux : une clause `applies_if` « privé » écarterait une aide que la commune dépose. Un seul propriétaire = comportement strictement identique à avant. « Propriété mixte » (`mixte`) n'est plus proposée au choix (`groupesProprietaire`) mais reste valide : Mérimée peut la poser, et une fiche qui la porte l'affiche cochée pour qu'on puisse la retirer.

Même idée pour `monuments.type_edifice` (`text[]`, migrations `20260930072800` puis `20260930082523`) et ses deux précisions `affecte_au_culte` / `architecture_romane` : les faits constatifs sur la nature du bien (église ou chapelle, cultuel, roman, patrimoine juif, monument aux morts…) se déduisent de la fiche par `auto_source` (`DEDUCTIONS_TYPE_EDIFICE`), à l'**unanimité** des types cochés, sinon la question reste posée. La réponse au questionnaire prime toujours. Ne pas réintroduire d'attribut de segment sur `users` : il avait été branché sur le filtrage des aides, retiré une fois (migration `20260516180000`), puis supprimé entièrement.

Vocabulaire — **un monument n'est pas un projet**, et la distinction porte tout le modèle :

- Un **monument** (table `monuments`, routes `/app/monuments/...`) est le BIEN : identification, protection, propriétaire, état sanitaire (« en péril ? »). Il porte l'**offre qui le gouverne** (`monument.offre`, cf. « Les trois offres »), son **équipe** (`project_members`) et ses **documents** (`documents.monument_ids` — arrêté de protection, cadastre, photos).
- Un **projet** (table `projets`, routes `/app/projets/...`) est un CHANTIER sur ce monument. N projets par monument, chacun avec son cadrage (`travaux_envisages`), son `questionnaire`, son diagnostic, ses **dossiers**, ses **suivis d'aide**, sa propre **équipe** (`projet_members`) et ses propres **documents** (`documents.projet_ids`).

Les deux ont vécu confondus jusqu'à l'inversion de hiérarchie (migrations `20260827105636` / `20260827105649`) : le « projet » était alors une ligne de `monuments`. `dossiers` et `aide_suivis` portent depuis un `projet_id` **et** un `monument_id` — ce dernier volontairement dénormalisé, parce que les requêtes batch du dashboard restent clés monument.

### Les deux niveaux de partage

Migration `20260827132033`. C'est la règle d'accès la plus délicate du produit :

- **Équipe du monument** (`project_members`) : voit tout — la fiche, TOUS les projets, les documents du monument et ceux de ses projets.
- **Équipe d'un projet** (`projet_members`, rôles `co_owner` / `member` seulement) : ne voit QUE ce chantier — ses aides, ses dossiers, ses documents, plus la fiche sanitaire du monument **en lecture**. Ni les autres projets, ni les documents du monument, ni son équipe.

Le rôle **effectif** sur un projet est le `max_role` des deux : un co_owner du monument reste co_owner de chacun de ses chantiers sans ligne dans `projet_members`. On ne restreint jamais un droit acquis un cran plus haut.

Trois conséquences à ne pas oublier en touchant à l'accès :

- `Monument.myRole` est **nul** pour un membre projet-seulement — c'est un accès restreint, pas un refus. `require_monument_read` rend ce `None` ; le confondre avec un droit d'écriture ouvre une faille. Les écritures passent toujours par `require_project_access`, qui refuse ces gens-là.
- Le front lit les droits d'une page projet sur **`Projet.myRole`**, jamais sur `Monument.myRole`.
- Les listes sont filtrées **côté serveur** (`list_projets`, `/dashboard`, `list_documents`) : masquer à l'affichage laisserait fuiter dans la réponse l'existence des autres chantiers.

## Les trois offres

Migration `20260902152215`. Rien de ce qui suit n'est décidé dans un composant : la table des droits vit à un seul endroit par côté, et les deux doivent rester d'accord.

| | Gratuit | Veille | Multi-monuments |
|---|---|---|---|
| Prix | 0 € | sur demande | sur demande |
| Canal | — | « Nous contacter » | « Nous contacter » |
| Monuments | 1 | 1 | illimités |
| Projets par monument | 2 | illimités | illimités |
| Détail des aides ouvertes | ✓ | ✓ | ✓ |
| Aides « Disponibles bientôt » | nommées mais floutées, modalités retirées | ✓ | ✓ |
| Échéancier d'un projet | flouté + paywall | ✓ | ✓ |
| Emails (nouvelles aides, ouverture de guichet, échéances) | ✗ | ✓ | ✓ |
| Inviter (onglet Équipe) | flouté + paywall | ✓ | ✓ |
| Supprimer un projet | ✗ | ✓ | ✓ |
| Tableau de bord | flouté + paywall | flouté + paywall | ✓ |
| Supprimer un monument | ✗ | ✗ | ✓ |

- La table des droits : [backend/services/offres.py](backend/services/offres.py) et son miroir [frontend/src/lib/offres.ts](frontend/src/lib/offres.ts). Les deux sont figées par des tests qui assertent les mêmes valeurs — un bouton affiché que le serveur refuse est le pire des deux mondes.
- **Multi-monuments contient Veille.** Les droits se cumulent par union des plans (`offre_pour`), jamais par « le premier plan trouvé » : le temps d'une montée en gamme, deux abonnements sont actifs.
- Un abonnement dont `plan` est NULL (antérieur aux trois offres) n'ouvre **rien**.
- **Tout compte créé depuis le 2026-09-07 reçoit Multi-monuments d'office.** `PLAN_A_LA_CREATION` dans [services/offres.py](backend/services/offres.py) porte la décision, `stripe_billing.octroyer_offre_initiale` l'applique aux quatre routes d'inscription (mot de passe, collaborateur, et leurs miroirs OAuth). L'octroi est une ligne `subscriptions` `active` sans contrepartie Stripe — clé primaire `octroi:<user_id>` (aucun id Stripe ne peut la percuter), ni prix ni `current_period_end`, donc rien à facturer et `access.portail` reste faux. Passer par la table des abonnements plutôt que par un drapeau sur `users` garde `offre_du_compte` seule autorité sur les droits. Les comptes antérieurs ne sont **pas** rattrapés, et refermer le robinet = remettre `PLAN_A_LA_CREATION` à `None` (les comptes déjà ouverts gardent leur ligne). L'offre gratuite reste donc décrite dans la table, mais plus personne n'y arrive par inscription.
- **Un rôle de compte ouvre Multi-monuments d'office** (`stripe_billing.PLAN_DES_ROLES`), sans ligne d'abonnement ni facturation : l'administrateur parce que `/admin` s'exploite en regardant le produit, le bêta-testeur parce qu'on ne lui fait pas essayer une moitié de produit (cf. « Les rôles de compte »). Le plan est **synthétisé à la lecture** (dans `active_plans`, `plans_par_compte` et `access_snapshot`), pas écrit comme un octroi — le droit suit ainsi les rôles dans les deux sens, et n'écrase jamais un abonnement réel puisqu'il entre par l'union des plans. `access.subscription` reste celle de Stripe : offre pleine, aucune échéance, pas de portail. **Quels rôles ouvrent l'offre se décide dans `roles.ROLES_AVEC_OFFRE`**, jamais dans la base ni dans `stripe_billing`.
- **Rien ne s'achète en libre-service** : `PLANS_VENDABLES` est VIDE, des deux côtés (`services/offres.py` et `lib/offres.ts`). Les deux offres payantes se négocient — la page Tarifs affiche « Sur demande » et un `mailto`, et `POST /billing/checkout` refuse tout en **409**. Elles restent des offres de plein droit, et Stripe reste l'outil de **facturation** (abonnement créé dans le dashboard, webhook qui l'enregistre, portail client), plus le tunnel de vente. Ouvrir la vente d'une offre = l'ajouter à `PLANS_VENDABLES` des DEUX côtés, poser son prix dans `STRIPE_PRICE_*`, et rendre son bouton à `startCheckout`.
- Aucun montant n'est écrit dans le code. Le jour où un prix devient public, il viendra de Stripe via `/billing/plans` : un prix affiché qui diffère du prix débité est le pire défaut possible sur une page de paiement.
- `access.portail` dit si le portail Stripe existe pour ce compte, et ne se déduit PAS de la détention d'une offre : une offre ouverte directement en base n'a pas de Customer, et « Gérer mon abonnement » y répondrait 404.
- Les garde-fous serveur sont dans [backend/services/quotas.py](backend/services/quotas.py), appelés par les routes de création, de suppression et d'invitation. Ils répondent **402** (offre manquante) et non 403 (droits d'équipe) : le front distingue les deux.
- **Rien ne disparaît, tout se floute.** Le paywall se pose DEVANT le contenu réel plutôt que de rediriger ou d'effacer : [components/shared/Paywall.tsx](frontend/src/components/shared/Paywall.tsx) expose `PaywallOverlay` (en place, contenu flouté et `inert` derrière) et `PaywallDialog` (en modale, pour les ACTIONS — « Nouveau monument », « Nouveau projet » — où il n'y a rien à montrer en aperçu et où refermer doit laisser l'utilisateur sur place). Les onglets et les boutons gardent donc leur libellé, leur destination et leur geste. Deux exceptions : les SUPPRESSIONS disparaissent sans un mot (vendre le droit de supprimer se lit mal), et l'équipe déjà constituée après une résiliation reste ouverte avec un simple `OffreUpsell` (un paywall par-dessus rendrait le retrait d'un membre impossible).
- **Le flou ne protège rien.** Ce qui est flouté est soit une VUE sur les données du compte (tableau de bord, équipe, échéancier), où il n'y a rien à cacher, soit — pour les aides à venir — leur vrai nom, envoyé en clair et lisible dans l'onglet Réseau des devtools. C'est une décision produit assumée du 2026-09-03, tenable parce que le catalogue vient de sources publiques et que l'offre ne vend pas le nom mais l'email d'ouverture et la fiche. Ne pas l'étendre par imitation : pour tout contenu qu'on veut réellement retenir, la frontière reste le serveur. Corollaire pour les aides : les chiffres qui portent l'argumentaire (montant, nombre) vont DANS la carte du paywall, pas derrière le flou où ils seraient illisibles.
- **Un clic n'est pas une arrivée.** Le garde de route `/app` rend le tableau de bord flouté, mais `?tab=equipe` gardé en favori retombe sur l'onglet par défaut plutôt que d'ouvrir un paywall : cliquer est une demande, arriver par un lien ne l'est pas.
- **L'offre gouverne l'AJOUT, jamais le RETRAIT.** Inviter demande Veille ; retirer un membre reste ouvert au gratuit. Une résiliation laisse les collaborateurs en place, et renvoyer alors vers les tarifs rendrait leur accès irrévocable — d'où `equipeAccessible = offre.equipe || equipe déjà constituée` sur les deux pages (l'onglet s'ouvre, pour gérer ce qui est là), et `TeamPanel.invitationsOuvertes` qui ne gouverne que le formulaire d'invitation.

Sur QUI porte un droit, et c'est le seul point délicat :

- **Compte** (`GET /billing/access` → `offre`) : enregistrer un monument, le tableau de bord, les emails de rappel.
- **Monument** (`monument.offre`, posé par `fetch_user_monuments` et `_enrich_monument`) : ses projets, son calendrier, son équipe, ses suppressions. C'est l'**union** de l'offre du propriétaire et de celle de l'appelant — sans le propriétaire, l'architecte invité par un client abonné se verrait refuser ce que son client paye ; sans l'appelant, on retirerait à un abonné un droit qu'il paye. Même idiome que `max_role` sur les deux niveaux de partage.

Le point de branchement des emails de veille est `stripe_billing.peut_recevoir_rappels(supabase, user_id)` : tout job de rappel doit l'appeler pour chaque destinataire, en plus de ses préférences de notification (l'offre décide du droit au service, les préférences du souhait).

## Architecture

```
frontend/   SPA React 19 + Vite + TS + Tailwind 4 + shadcn/ui + Zustand   → app.monumia.fr
landing/    site vitrine statique React                                    → monumia.fr
backend/    FastAPI (Python 3.12, uv) + Uvicorn                            → /api
supabase/   migrations PostgreSQL (Auth JWT, Storage bucket `documents`)
nginx/      reverse proxy + Certbot ; docker-compose gère prod + beta
```

Backend : [main.py](backend/main.py) monte 17 routers ([backend/routers/](backend/routers/)), [db.py](backend/db.py) expose les clients Supabase (service-role en singleton, anon par requête pour l'auth) et vérifie les JWT localement via JWKS, [config.py](backend/config.py) tient `ALLOWED_ORIGINS` — une seule liste sert à la fois au CORS et aux redirections de retour Stripe.

Frontend : un store Zustand et un service par domaine (`src/stores/`, `src/services/`), types dans `src/types/`, logique métier pure testable dans `src/lib/`.

## Le pipeline de diagnostic

C'est le point le plus important à comprendre avant de toucher au matching.

Un seul moteur, déterministe : `POST /aides/diagnostic-deterministe` → [eligibility_engine.py](backend/eligibility_engine.py). Il lit les YAML `backend/data/aides/*.yaml` (id = **slug**), ne fait **aucun appel réseau** (~2 ms/diagnostic, YAML en cache) et ne persiste **rien** : le QCM se résout côté client via `eliminationsParOption`. Le front passe partout par `runProjectDiagnostic(projetId, answers)` (wizard, page projet, liste, dashboard).

Le moteur ne connaît **pas** les projets : `FIELD_REGISTRY` et `build_context` lisent toujours `travaux_envisages` sur le monument. La fusion se fait à la frontière, dans `merge_projet_into_monument` ([aides.py](backend/routers/aides.py)) : fiche du monument + cadrage du projet. Ne pas la déplacer dans le moteur. La requête accepte `projet_id` (chemin normal) ou `monument_id` seul (compat d'un onglet SPA non rechargé, résolu vers le projet ouvert le plus récent) ; l'offre appliquée reste celle du monument dans les deux cas.

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

Les tâches de catalogue passent par le paquet `backend/catalogue/` (refonte d'octobre 2026, cf. [docs/refonte-pipeline/rapport-final.md](docs/refonte-pipeline/rapport-final.md)) : une commande planifiable, `uv run python -m catalogue semaine`, enchaîne la veille (détection et application des changements de source, mandat volontairement étroit : jamais `kind`/`effect`/`fact`/`field`), l'entrée au catalogue d'un quart des territoires et l'ingestion des pages admises. Tout ce qui se règle (modèle par rôle, décisions et seuils, budgets, et quelle chaîne tient chaque opération pendant la transition) est dans `backend/data/catalogue/registre.yaml` ; l'état et l'historique des décisions sont dans `backend/data/catalogue/journal/` ; ce que le run ne tranche pas devient une case à cocher dans `data/reviews/AAAA-MM-JJ-semaine.md`. La cohérence du typage passe par l'espace d'embedding (`backend/catalogue/espace.py`, décisions `C1-coherence` et `F3-famille-fait`) : l'agent d'ingestion voit la famille d'un critère (outil `conditions_voisines`) et celle d'un fait qu'il propose, une condition typée autrement que ses voisines devient une case, et l'étape `coherence` du run audite le stock. Les vecteurs vivent hors du dépôt (`~/.local/share/monumia/plongements.sqlite`), les jugements de Jev dans `backend/data/catalogue/coherence/jugements.jsonl` (suivi par git), les écarts déjà tranchés dans `backend/data/catalogue/coherence/ecarts-acceptes.yaml`. Les skills `/ingest-aide` et `/rediger-fiche` restent l’outil à la main dans Claude Code.

L'ancienne chaîne (`scripts/prospecter.py`, `scripts/ingerer.py`, `scripts/balayage.py`, `scripts/veille_aides.py`) reste exécutable comme filet de retour, pour chaque opération que le registre lui laisse ; un ancien script refuse de tourner sur une opération que le registre donne à la nouvelle chaîne. Les deux chaînes CHARGENT le SKILL.md correspondant comme prompt (la doctrine des étapes 2 et 3 de `prospecter-aides-region`, le protocole d'`ingest-aide` pour l'agent) : modifier un skill change le pipeline le jour même, et change l'empreinte sur laquelle les seuils de Jev ont été mesurés (un test du registre échoue tant qu'ils ne sont pas remesurés). Détails dans [backend/data/README.md](backend/data/README.md) ; recettes de balayage par territoire dans `backend/data/prospection/territoires.yaml`.

**Large sur les THÈMES, strict sur le DESTINATAIRE** (décision du 2026-09-21). Le spectre thématique ne bouge pas — énergie, eau, jardins, tourisme, accessibilité, numérique, spectacles, activité économique y restent tous. Ce qui décide de l'entrée est **à qui la source s'adresse, et en quelle qualité** : une aide entre si elle vise celui qui possède ou gère un LIEU, pris en cette qualité, pour ce lieu ou ce qui s'y tient ; elle sort si elle vise quelqu'un pour son MÉTIER (agriculteur, compagnie, artiste, PME en général, ménage), même si un propriétaire de monument peut aussi être cela. La question opérante : « un propriétaire de monument peut-il déposer cette demande tel qu'il est, pour son monument, sans changer de métier ni créer une structure pour l'occasion ? » Le test complet et sa table de cas frontière sont à l'**étape 3 du skill `prospecter-aides-region`**, qui est la source unique : `tri.doctrine()` l'extrait, la lecture et la requalification la relisent.

- La lecture rend deux jugements DESCRIPTIFS — `destinataire` et `objet` — et le CODE en dérive la décision (`pipeline.etat.retenir`). `retenir` n'est plus une valeur du modèle : le défaut « retenir » faisait passer 57 % des candidates douteuses du tri (497 sur 869), jusqu'à des concours de pâtisserie et des aides à la plantation de kiwis.
- **Jev juge avant le LLM de lecture** (décision `E1-entree` du registre, questions dans `prospection/arbitre.py`). Jev est un modèle de décision : il rend des probabilités, jamais de texte. Sous 0,12 la page est écartée sans LLM ; au-dessus, le LLM de lecture reçoit sa consigne complète et un écart du LLM entre 0,12 et 0,57 devient `indetermine`. Raison mesurée le 2026-10-04 : le LLM seul écartait à tort 11,4 % des aides gardées, Jev 0,7 %, à relecture humaine égale. Le verdict corrigé s'écrit dans `destinataire` / `objet` / `categorie_ecart` (les champs que relit `motif_non_promotion`), jamais à côté. Changer les questions ou les seuils impose de remesurer (`python -m catalogue calibrer`, cf. [docs/jev.md](docs/jev.md)). Jev en panne : la nouvelle chaîne laisse la page due, sans repli sur le LLM seul.
- `indetermine` est le défaut des deux champs, et c'est une TROISIÈME issue : la candidate reste `a_valider`, `promouvables` la retient, et `prospecter.py valider <territoire>` la liste avec son motif. Elle n'est ni ingérée, ni perdue.
- Une écartée entre en `ignore` dans la file avec son motif — elle ne revient plus au balayage suivant, ce qui n'était pas le cas quand elle n'y entrait simplement pas.
- À l'ingestion, la source peut révéler ce que le titre taisait : `declarer_hors_perimetre` arrête le travail sans écrire de YAML, et c'est un résultat normal.
- Ce qu'une aide retenue à tort coûte VRAIMENT, mesuré sur le balayage des quatre régions du 2026-09-18 : pas « une ingestion » que ses conditions typées élimineront plus tard, mais en moyenne un fait neuf dans l'ontologie (563 faits pour 643 aides, 77 % cités par une seule), des questions qui entrent dans le tronc commun de tous les propriétaires (profil « association, inscrit, CVL » : 20 → 35 questions), et des heures de relecture. Une aide écartée à tort disparaît sans recours — d'où `indetermine`, qui ne tranche ni dans un sens ni dans l'autre.

Ancienne chaîne : `ingerer.py --file-attente` prend **toute la file**, pas le seul run qui vient de tourner : le balayage du 2026-09-18 a ainsi ingéré 76 aides de territoires qu'il ne balayait pas (Eure, Pays de la Loire, Hauts-de-France). `--territoire` borne.

Le pipeline s'arrête exactement là où s'arrête un skill : il écrit dans le working tree, produit une fiche de review par aide, et n'exécute **jamais** `git add`, un commit, ni `load_aides_yaml.py`. Une panne n'est jamais un jugement : elle laisse l'objet dû pour le run suivant. Une aide en service n'est jamais remplacée par une version refusée ; une aide neuve refusée va dans `data/catalogue/rebuts/`, hors de `data/aides/`. L'ancienne chaîne, elle, renomme une aide refusée en `<slug>.yaml.echec`, hors du glob `*.yaml` — invisible au lint, au moteur et au loader.

**Pas de `git commit` pendant qu'un run de l'ancienne chaîne (`ingerer.py`, `prospecter.py`) tourne**, même depuis un autre terminal ou une autre session. pre-commit met de côté les modifications non indexées le temps des hooks : `file-attente.yaml`, `facts_pending.yaml` et `facts.yaml` reviennent à leur version HEAD pendant quelques secondes, et le run lit alors des fichiers d'un autre âge. Vu le 2026-09-13 : lint rouge sur cinq faits pourtant présents, et orchestrateur tué par un slug « absent de la file ». `python -m catalogue semaine` n'y est plus exposé : il travaille dans une copie jetable du dépôt et ne recopie rien si un fichier a bougé pendant le run (code 8). Ancienne chaîne : un `en_cours` sans processus vivant est une orpheline : `--reprendre` la ré-ingère ; si son journal `data/reviews/logs/ingest-<slug>.log` dit déjà « OK », corriger le statut à la main plutôt que repayer l'ingestion.
### La surcouche d'exploitation (page `/admin`)

Seule exception à « `data/` est la source de vérité » : trois tables que le loader ne touche jamais, appliquées PAR-DESSUS le cache YAML au moment de servir — `aides_retirees` (retirer une aide du catalogue), `faits_surcharges` (reformuler une question du QCM, son aide contextuelle, ses réponses) et `conditions_predicats` (remplacer le prédicat d'une condition). Migrations `20260911201246` et `20260913103327`, mécanique dans [backend/services/catalogue_admin.py](backend/services/catalogue_admin.py), routes dans [backend/routers/admin.py](backend/routers/admin.py), page front sur `/admin`.

- Le YAML reste la vérité **éditoriale**. Un retrait durable se fait en archivant l'aide dans `data/`, une reformulation durable en corrigeant `facts.yaml`, un critère corrigé durablement en modifiant `data/aides/<slug>.yaml` — puis on rétablit la ligne en base, sinon elle fige la version d'avant et la correction du YAML reste sans effet.
- **Un seul point de branchement** : `deterministic_diagnostic_for` ([routers/aides.py](backend/routers/aides.py)), le funnel unique des trois diagnostics (projet, invité, dashboard). Il couvre du même coup les quatre seaux, `totalAidesAnalysees`, l'échéancier, les vignettes et le QCM. `supabase=None` rend le moteur nu (tests du moteur, scripts hors ligne).
- Une aide retirée est **404 partout** : `GET /aides/{id}` et `POST /dossiers`, sans exemption `_deja_engage` — contrairement au paywall des guichets à venir, où l'exemption existe.
- **Les ids des réponses sont figés**, les libellés non : les prédicats des aides citent les ids. Renommer est sans risque, supprimer casse un prédicat — d'où `POST /admin/faits/{key}/simuler`, qui montre avant l'enregistrement ce que chaque réponse écarte et quelles aides citent celle qu'on retire. Une réponse NOUVELLE est hors de tout prédicat, donc écartante par construction : vérifier son impact avant d'enregistrer.
- Les réponses sont éditables sur un `enum`, un `multi_enum` **ou un `boolean`** ; seules les tranches d'un fait numérique restent calculées par le moteur depuis les seuils des aides (`_options_for_fact`), elles ne viennent pas du YAML.
- **Un booléen peut offrir plus de deux réponses.** Chacune déclare la `valeur` qu'elle envoie aux prédicats des aides — `true`, `false`, ou `null` (« ne tranche pas » : le fait reste inconnu, la condition reste une incertitude, l'aide n'est jamais écartée). Les prédicats des aides ne bougent pas, ils restent `eq: true` / `eq: false` : c'est tout l'intérêt du dispositif. Cinq règles tiennent dans `FactDef._options_coherentes`, dont la première porte toute la compatibilité ascendante — un booléen qui déclare ses options **doit garder `oui` (true) et `non` (false)**, sinon les réponses déjà enregistrées dans `projets.questionnaire` changeraient de sens sous les utilisateurs. `OPTIONS_BOOLEEN_IMPLICITES` est la définition unique du couple par défaut, lue par le moteur ET par l'administration.
- **La valeur de test n'est pas l'identifiant.** Sur un fait à choix, l'identifiant EST la valeur ; sur un booléen, c'est la `valeur` déclarée. `_normalize_answer` (moteur) et `_valeur_de_test` (impact admin) doivent bouger ensemble : `evaluate_predicate({"eq": True}, "oui")` vaut `False`, et l'écran annoncerait que « Oui » écarte les aides qui exigent « oui ».
- **Le prédicat d'une condition se modifie aussi** (troisième table, `conditions_predicats`, migration `20260913103327`). Mandat étroit, énoncé une seule fois dans `condition_modifiable` : gate `user_fact` sur un fait à options, prédicat de forme simple — aucun combinateur, l'interface ne saurait pas le rendre. Le corps de requête porte un **opérateur et des valeurs**, jamais un prédicat JSON brut : la contrainte « impossible de produire un prédicat invalide » est tenue par le type. `check_fact_predicate` a été remontée du lint dans [aides_schema.py](backend/aides_schema.py) pour que la validation y soit mot pour mot celle du lint (le lint réimporte le nom, `veille_apply` et `veille_typage` ne changent pas).
- **Une surcharge de prédicat périme toute seule.** Elle mémorise les trois témoins de ce qui a motivé la décision — `condition_text`, `fact_key`, `predicate_origine` — et les recompare à chaque passage (patron de `traiter_acquittements`). Le texte change → `perimee_texte`, le fait change → `perimee_fait` : la ligne n'est plus appliquée. Le prédicat YAML change sans le texte → `a_revoir`, et là **la ligne s'applique quand même** : ignorer un correctif parce que le YAML a rattrapé re-casserait en silence ce que l'administrateur avait réparé. C'est la seule asymétrie de la cascade. La comparaison des textes se fait sur l'empreinte `" ".join(text.split())`, sinon un simple re-repli du YAML périmerait toutes les surcharges d'une fiche.
- Une surcharge de prédicat peut citer une réponse qui n'existe que dans `faits_surcharges` : les deux forment alors un **bloc indissociable** au moment du report vers le YAML — reporter l'une sans l'autre laisse un prédicat qui cite une option inexistante.
- Cache module-level, **TTL 60 s + invalidation après chaque écriture** : un seul process uvicorn par environnement, donc l'invalidation vaut pour tous ; le TTL n'est qu'un filet pour une ligne modifiée dans Supabase Studio. Une lecture qui échoue (migration pas encore appliquée) rend une surcouche vide et sert les YAML — un retrait est une correction éditoriale, pas une frontière de sécurité.
- Corollaire moteur : `_normalize_answer` rend `None` pour un id d'option inconnu (fail-closed). Une réponse déjà persistée sur une option supprimée éliminerait sinon des aides pour toujours.

### Les rôles de compte

Table `comptes_roles` (migrations `20260916062229` puis `20260916064516`), mécanique dans [backend/services/roles.py](backend/services/roles.py), onglet « Rôles » de `/admin`. À ne pas confondre avec les **rôles d'équipe** (`co_owner` / `member`, cf. « Les deux niveaux de partage ») : ceux-ci portent sur le compte entier.

- Deux rôles, et **un seul est un droit d'administration** : `admin` ouvre `/admin` ; `beta_testeur` n'ouvre RIEN d'autre que l'offre. C'est toute la raison d'en avoir deux — donner l'offre sans donner le catalogue. Un compte peut cumuler les deux, et chaque ligne se retire séparément.
- L'écran part de la **liste des comptes** (`GET /admin/utilisateurs`) et bascule sur place : deux boutons alignés par ligne, en surbrillance quand le rôle est actif, un clic écrit tout de suite (`PUT`/`DELETE /admin/roles/{role}/{user_id}`). Pas de champ email à taper — on ne peut pas se tromper de destinataire, et on voit qui a déjà quoi. Les deux écritures sont **idempotentes** (un double-clic, deux onglets) et rendent la LIGNE du compte, que la page substitue à la sienne.
- **`modifiable` et `raison` viennent du serveur** (`roles._verrou`), miroir exact de ses deux 409 : un bouton qui part en erreur est un bouton qui n'aurait pas dû être cliquable. Un test parcourt la liste et vérifie que chaque bascule annoncée modifiable aboutit, et que chaque bascule bloquée refuse.
- La liste est plafonnée (`LIMITE_UTILISATEURS`), triée du plus récent au plus ancien, filtrée côté client — mais les **porteurs de rôle sont ajoutés en plus du plafond** : un droit attribué ne doit jamais devenir invisible, sinon il serait impossible de le retirer. Une liste tronquée le dit à l'écran.
- Le lot des rôles est fermé **trois fois** et les trois doivent rester d'accord : le `Literal` de la route, `roles.ROLES`, et la contrainte `check` de la base — un test le vérifie.
- `ADMIN_USER_IDS` reste lue, mais comme un **socle d'amorçage** et pour le seul rôle `admin` : elle ouvre la porte quand la table est vide (environnement neuf), ses comptes ne se retirent PAS depuis l'application, et elle peut être vidée du `.env` une fois les mêmes comptes inscrits en base. `est_admin` rend l'**union** des deux ; socle vide + table vide = aucun administrateur, jamais tous. Le profil porte `estAdmin` pour l'affichage ; l'autorité est `require_admin` ([db.py](backend/db.py)), posé sur le router entier — y compris sur les trois routes qui listent les comptes et attribuent les rôles.
- Deux refus tiennent la porte ouverte, tous deux propres à `admin` : **se retirer soi-même l'administration** (409) — c'est le seul geste qui pourrait fermer la page pour de bon, d'où la garantie qu'il reste toujours un administrateur — et **la retirer à un compte du socle** (409), que le `.env` rouvrirait aussitôt. Se retirer son propre bêta-test, lui, ne ferme rien et reste permis. Retirer un rôle non porté est idempotent et ne se plaint pas : une ligne orpheline doit pouvoir partir.
- La lecture de `comptes_roles` suit le patron de cache de la surcouche (TTL 60 s + invalidation), mais son repli va dans l'autre sens : une lecture qui échoue rend une liste **vide** et laisse le seul socle ouvrir la porte. Une surcouche de catalogue en panne est bénigne, un droit d'administration accordé parce qu'une requête a échoué ne l'est pas. Même fail-closed sur une ligne au rôle inconnu, écrite à la main dans Supabase Studio : elle est ignorée.

## Pièges connus

- **pyright n'analyse pas tout** : `pyproject.toml` exclut `scripts` et `routers`, et n'inclut que `*.py` racine + `services`. Une erreur de type dans un router ne sera vue ni en local ni en CI.
- **Deux espaces d'identifiants d'aides** cohabitent : slug (YAML, moteur déterministe) et UUID (`aides_v3`). `GET /aides/{id}` résout dans cet ordre UUID puis slug. La création de dossier passe par `aides_v3`, d'où l'étape de sync YAML → base à la fin de `deploy.sh` : une aide en YAML mais absente de `aides_v3` renvoie « Aide introuvable » à la création de dossier.
- **`vitest.config.ts` utilise `environment: 'node'`** : un test de composant React a besoin d'un environnement DOM explicite.
- **Le détail des aides est gratuit.** Ce qui reste retenu ne concerne que les aides dont le guichet n'est pas encore ouvert, et ce n'est plus leur nom : `retirer_les_modalites` ([aides.py](backend/routers/aides.py)) leur ôte financeur, contacts, pièces et procédure, `redact_bientot_hors_offre` l'applique aux trois seaux à portée, et le seul contrôle qui tienne est le **402 sur `GET /aides/{id}`** — unique chemin vers la fiche complète, avec une exemption pour les aides déjà suivies (`_deja_engage`). `build_digest`, lui, masque ENCORE le nom (`masquer_bientot`) : il alimente l'échéancier et les vignettes de projet, qui ne sont pas floutés. `users.has_aides_access` et `monument_unlocks` ont été supprimés (migration `20260902152215`) ; ne pas les ressusciter.
- Les accès aux monuments partagés passent par `require_project_access(supabase, monument_id, user_id, role)` — un filtre `user_id` renverrait 404 aux collaborateurs. Pour un projet, c'est `require_projet_access(supabase, projet_id, user_id, role) -> (ligne, rôle)`, qui combine les deux appartenances. Pour la seule LECTURE d'une fiche monument, `require_monument_read` (cf. « les deux niveaux de partage »). La visibilité d'un document se tranche avec `best_document_role(monument_ids, projet_ids, …)`, jamais sur les seuls `monument_ids`.
- Sans `RESEND_API_KEY`, les emails (invitations, rappels) sont écrits en console (mode dev).
- **Les rappels par email** (`scripts/rappels_aides.py`, cron 9 h, cf. `scripts/cron-rappels.sh`) annoncent trois choses : une échéance qui approche (paliers réglables par compte, 30 jours par défaut), une aide fermée qui devient déposable, et une aide qui entre au catalogue guichet ouvert. Le basculement « Disponibles bientôt » → seaux du haut ne s'écrit toujours nulle part (`disponibilite()` le recalcule) : le job le CONSTATE en comparant chaque matin l'état d'ouverture du catalogue servi à l'instantané de la veille (`aides_veille_etat`, rempli sans rien annoncer au premier passage). Une aide disponible n'est annoncée qu'aux projets où le diagnostic la met dans l'un des trois seaux du haut : elle passe les critères automatiques et aucune réponse déjà donnée ne l'écarte, un fait jamais demandé restant une incertitude. Un compte reçoit au plus UN email par passage (échéances et aides disponibles, tous projets confondus), et chaque rappel ne part qu'une fois : `aide_rappels_envoyes` est ce journal anti-doublon, clé (projet, aide, nature, palier, date annoncée), si bien qu'une échéance à J-29 retombe sur la clé déjà journalisée à J-30. Le job passe par `peut_recevoir_rappels` pour chaque compte, avant même de lire ses préférences de notification.
