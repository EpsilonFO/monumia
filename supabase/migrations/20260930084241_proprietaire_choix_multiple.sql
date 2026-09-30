-- Propriétaire du monument en CHOIX MULTIPLE.
--
-- Un bien peut appartenir à plusieurs propriétaires de natures différentes :
-- une église communale dont le presbytère est à une association, un château
-- indivis entre une SCI et une personne physique. `monuments.proprietaire`
-- passe donc de `ownership_type` à `ownership_type[]`, et chaque fiche
-- existante devient un tableau d'un élément.
--
-- On garde le type énuméré plutôt qu'un `text[]` à contrainte : c'est déjà lui
-- qui ferme la liste (migration 20260705120000 pour `public_epci` et
-- `syndicat_mixte`), en accord avec `OWNERSHIP_LABELS` (backend/labels.py) et
-- `OWNERSHIP_TYPES` (frontend/src/constants/monument-options.ts). La colonne
-- reste NOT NULL ; un tableau vide est refusé par la contrainte : un monument
-- a toujours au moins un propriétaire.
--
-- Sémantique (décision du 2026-09-30, « il suffit d'un seul ») : une aide est
-- proposée dès qu'UN des propriétaires cochés peut la déposer. Le moteur
-- évalue l'aide une fois par propriétaire et garde le meilleur verdict
-- (eligibility_engine.run_deterministic_diagnostic) ; les prédicats des aides
-- restent écrits sur une valeur.
--
-- Aucune vue, fonction, politique RLS ni index ne lit cette colonne (vérifié
-- sur les migrations et sur pg_proc / pg_depend / pg_policy / pg_indexes).

alter table public.monuments
    alter column proprietaire type public.ownership_type[]
    using array[proprietaire];

alter table public.monuments
    drop constraint if exists monuments_proprietaire_non_vide;

alter table public.monuments
    add constraint monuments_proprietaire_non_vide check (cardinality(proprietaire) > 0);

comment on column public.monuments.proprietaire is
    'Propriétaires du bien, un ou plusieurs (backend/labels.py, OWNERSHIP_LABELS). Une aide est proposée dès qu''un seul d''entre eux peut la déposer.';
