-- Suivi du statut des aides par projet (monument) + clôture de projet.
-- Table légère : un suivi par couple (monument, aide). Le dossier reste optionnel.

create type public.aide_suivi_statut as enum (
    'a_faire', 'en_preparation', 'depose', 'accorde', 'refuse'
);
create type public.aide_refus_motif as enum (
    'inegibilite', 'budget_epuise', 'dossier_incomplet',
    'non_prioritaire', 'hors_delai', 'autre'
);

create table if not exists public.aide_suivis (
    id uuid not null default gen_random_uuid(),
    monument_id uuid not null references public.monuments (id) on delete cascade,
    -- aide_id : référence logique vers le catalogue d'aides (stocké en text comme
    -- dossiers.aide_id) ; pas de FK stricte car le catalogue est géré séparément.
    aide_id text not null,
    user_id uuid not null references auth.users (id) on delete cascade,
    statut public.aide_suivi_statut not null default 'a_faire',
    montant_obtenu numeric null,
    motif_refus_code public.aide_refus_motif null,
    motif_refus_detail text null,
    note text null,
    historique jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint aide_suivis_pkey primary key (id),
    constraint aide_suivis_montant_positif check (montant_obtenu is null or montant_obtenu >= 0),
    constraint aide_suivis_unique_couple unique (monument_id, aide_id)
);

create index if not exists idx_aide_suivis_monument on public.aide_suivis using btree (monument_id);
create index if not exists idx_aide_suivis_user on public.aide_suivis using btree (user_id);

-- RLS : propriétaire seul (defense-in-depth ; le backend service-role vérifie aussi).
alter table public.aide_suivis enable row level security;

create policy "aide_suivis: select own"
  on public.aide_suivis
  as permissive
  for select
  to authenticated
  using (auth.uid() = user_id);

create policy "aide_suivis: insert own"
  on public.aide_suivis
  as permissive
  for insert
  to authenticated
  with check (
    auth.uid() = user_id
    and exists (
      select 1 from public.monuments m
      where m.id = monument_id and m.user_id = auth.uid()
    )
  );

create policy "aide_suivis: update own"
  on public.aide_suivis
  as permissive
  for update
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "aide_suivis: delete own"
  on public.aide_suivis
  as permissive
  for delete
  to authenticated
  using (auth.uid() = user_id);

-- Clôture de projet (null = ouvert).
alter table public.monuments add column if not exists cloture_at timestamptz;
