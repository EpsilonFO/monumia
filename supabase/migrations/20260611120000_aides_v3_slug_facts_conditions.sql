-- Données d'aides déclaratives (backend/data/*.yaml) — étape 1.
--
-- 1. `slug` sur aides_v3 : identité stable pour l'upsert du loader
--    (backend/scripts/load_aides_yaml.py). `verified_at` : date de dernière
--    vérification humaine contre la source officielle.
-- 2. `facts` : ontologie des faits (questions canoniques typées) — miroir de
--    backend/data/facts.yaml.
-- 3. `aide_conditions` : conditions d'éligibilité typées, une ligne par puce —
--    miroir du bloc `conditions` des YAML. Remplacera à terme le champ texte
--    aides_v3.conditions_eligibilite_detail (conservé pendant la transition
--    pour le moteur LLM actuel / le shadow mode).

alter table public.aides_v3
    add column if not exists slug text,
    add column if not exists verified_at date;

create unique index if not exists idx_aides_v3_slug
    on public.aides_v3 (slug)
    where slug is not null;

create table if not exists public.facts (
    key text primary key,
    type text not null check (type in ('boolean', 'integer', 'number', 'enum')),
    scope text not null check (scope in ('monument', 'projet', 'proprietaire')),
    question text not null,
    options jsonb,          -- [{id, label, unknown}] pour type=enum
    unit text,
    help text,
    auto_source text
);

-- Garantit la PK d'aides_v3 avant la FK ci-dessous. Sur certaines bases la
-- contrainte aides_v3_pkey (posée par 20260405170500_remote_schema) a été
-- supprimée hors-migration ; sans contrainte unique sur (id), la FK échoue avec
-- SQLSTATE 42830. Le bloc est idempotent (no-op si la PK existe déjà).
do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conrelid = 'public.aides_v3'::regclass
          and contype = 'p'
    ) then
        alter table public.aides_v3
            add constraint aides_v3_pkey primary key (id);
    end if;
end
$$;

create table if not exists public.aide_conditions (
    id uuid primary key default gen_random_uuid(),
    aide_id uuid not null references public.aides_v3 (id) on delete cascade,
    position integer not null,
    condition_key text not null,
    text text not null,
    kind text not null check (
        kind in ('untyped', 'auto', 'user_fact', 'discretionary', 'info', 'manual_check')
    ),
    effect text not null default 'gate' check (effect in ('gate', 'modulateur', 'info')),
    fact_key text references public.facts (key),
    field text,
    predicate jsonb,
    applies_if jsonb,
    quote text,
    notes text,
    unique (aide_id, condition_key)
);

create index if not exists idx_aide_conditions_aide on public.aide_conditions (aide_id);
create index if not exists idx_aide_conditions_fact on public.aide_conditions (fact_key);

-- RLS : miroir d'aides_v3 — tables référentielles, lecture pour les
-- utilisateurs authentifiés, écritures réservées au service_role (bypass RLS).

alter table public.facts enable row level security;
drop policy if exists "facts_read" on public.facts;
create policy "facts_read"
    on public.facts
    as permissive
    for select
    to authenticated
    using (true);

alter table public.aide_conditions enable row level security;
drop policy if exists "aide_conditions_read" on public.aide_conditions;
create policy "aide_conditions_read"
    on public.aide_conditions
    as permissive
    for select
    to authenticated
    using (true);
