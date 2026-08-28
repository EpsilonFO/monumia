-- Inversion de la hiérarchie : un MONUMENT porte désormais N PROJETS de travaux.
--
-- Avant : « projet » = ligne de `monuments`, qui portait le cadrage
-- (travaux_envisages, questionnaire, cloture_at). Après : le monument reste la
-- fiche du bien (identification, protection, propriétaire, état sanitaire) et
-- chaque chantier vit dans une ligne `projets`, avec son propre questionnaire.
--
-- Le paywall, le partage d'équipe et les documents restent clés MONUMENT : rien
-- n'y change. Seuls les dossiers et les suivis d'aide descendent d'un cran.

create table public.projets (
    id uuid not null default gen_random_uuid(),
    monument_id uuid not null references public.monuments (id) on delete cascade,
    user_id uuid not null references auth.users (id) on delete cascade,
    -- Nullable : le titre est dérivable des raisons / travaux, on ne force pas
    -- l'utilisateur à nommer son chantier avant de savoir ce qu'il contient.
    titre text,
    -- `{}` est une réponse à part entière (« Pas encore déterminé ») : le
    -- hard_filter travaux du moteur est fail-open sur liste vide.
    travaux_envisages text[] not null default '{}',
    -- Réponses au QCM + clés réservées (`_raisons`), persistées telles quelles.
    questionnaire jsonb,
    -- null = projet ouvert (repris de monuments.cloture_at).
    cloture_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint projets_pkey primary key (id)
);

create index if not exists idx_projets_monument on public.projets using btree (monument_id);
create index if not exists idx_projets_user on public.projets using btree (user_id);

drop trigger if exists projets_updated_at on public.projets;
create trigger projets_updated_at before update on public.projets
  for each row execute function public.update_updated_at();

-- Défense en profondeur : le propriétaire d'un projet est immuable, comme sur
-- monuments / dossiers / documents.
drop trigger if exists lock_owner on public.projets;
create trigger lock_owner before update on public.projets
  for each row execute function public.prevent_owner_change();

-- RLS garde-fou (patron aide_suivis) : le backend passe par le service-role et
-- vérifie les droits applicativement (require_projet_access), mais un client
-- anon/authenticated ne doit jamais lire ou écrire le projet d'un autre.
alter table public.projets enable row level security;

create policy "projets: select own"
  on public.projets
  as permissive
  for select
  to authenticated
  using (auth.uid() = user_id);

create policy "projets: insert own"
  on public.projets
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

create policy "projets: update own"
  on public.projets
  as permissive
  for update
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "projets: delete own"
  on public.projets
  as permissive
  for delete
  to authenticated
  using (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- Backfill : le questionnaire actuel de chaque monument devient son 1er projet
-- ---------------------------------------------------------------------------

insert into public.projets (
    monument_id, user_id, travaux_envisages, questionnaire, cloture_at, created_at, updated_at
)
select
    m.id,
    m.user_id,
    coalesce(m.travaux_envisages, '{}'),
    m.questionnaire,
    m.cloture_at,
    m.created_at,
    m.updated_at
from public.monuments m
where m.questionnaire is not null
   or coalesce(array_length(m.travaux_envisages, 1), 0) > 0
   or m.cloture_at is not null;

-- Filet : un monument peut porter des dossiers ou des suivis sans avoir jamais
-- rempli de questionnaire (dossier ouvert depuis un diagnostic non enregistré).
-- Sans ce projet vide, le `set not null` plus bas ferait échouer la migration.
insert into public.projets (monument_id, user_id, created_at, updated_at)
select m.id, m.user_id, m.created_at, m.updated_at
from public.monuments m
where not exists (select 1 from public.projets p where p.monument_id = m.id)
  and (
    exists (select 1 from public.dossiers d where d.monument_id = m.id)
    or exists (select 1 from public.aide_suivis s where s.monument_id = m.id)
  );

-- ---------------------------------------------------------------------------
-- Dossiers et suivis deviennent enfants de projet
--
-- `monument_id` est CONSERVÉ, volontairement dénormalisé : tout le contrôle
-- d'accès (require_project_access), le paywall (has_monument_access) et les
-- requêtes batch du dashboard restent clés monument. Le retirer imposerait une
-- jointure à chaque garde.
-- ---------------------------------------------------------------------------

alter table public.dossiers
    add column if not exists projet_id uuid references public.projets (id) on delete cascade;

update public.dossiers d
set projet_id = p.id
from public.projets p
where p.monument_id = d.monument_id
  and d.projet_id is null;

alter table public.dossiers alter column projet_id set not null;
create index if not exists idx_dossiers_projet on public.dossiers using btree (projet_id);

alter table public.aide_suivis
    add column if not exists projet_id uuid references public.projets (id) on delete cascade;

update public.aide_suivis s
set projet_id = p.id
from public.projets p
where p.monument_id = s.monument_id
  and s.projet_id is null;

alter table public.aide_suivis alter column projet_id set not null;
create index if not exists idx_aide_suivis_projet on public.aide_suivis using btree (projet_id);

-- Le couple unique descend au grain projet : deux projets d'un même monument
-- peuvent suivre la même aide.
alter table public.aide_suivis drop constraint if exists aide_suivis_unique_couple;
alter table public.aide_suivis
    add constraint aide_suivis_unique_couple unique (projet_id, aide_id);
