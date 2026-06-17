-- Projets partagés : adhésions + invitations + type de compte collaborateur.
-- Le partage se fait au niveau du monument (= projet). Les droits sont appliqués
-- côté applicatif (backend) ; le RLS user_id existant reste un garde-fou.

-- 1. Membres ayant accès à un projet
create table if not exists public.project_members (
    id           uuid not null default gen_random_uuid(),
    monument_id  uuid not null references public.monuments(id) on delete cascade,
    user_id      uuid not null references public.users(id) on delete cascade,
    role         text not null check (role in ('owner', 'co_owner', 'member')),
    invited_by   uuid null references public.users(id),
    joined_at    timestamptz not null default now(),
    constraint project_members_pkey primary key (id),
    constraint project_members_unique unique (monument_id, user_id)
) TABLESPACE pg_default;

create index if not exists idx_project_members_monument on public.project_members using btree (monument_id) TABLESPACE pg_default;
create index if not exists idx_project_members_user on public.project_members using btree (user_id) TABLESPACE pg_default;

-- 2. Invitations en attente (avant création/rattachement du compte)
create table if not exists public.project_invitations (
    id           uuid not null default gen_random_uuid(),
    monument_id  uuid not null references public.monuments(id) on delete cascade,
    email        text not null,
    token        text not null,
    invited_by   uuid not null references public.users(id),
    status       text not null default 'pending'
                 check (status in ('pending', 'accepted', 'revoked', 'expired')),
    created_at   timestamptz not null default now(),
    expires_at   timestamptz not null,
    accepted_at  timestamptz null,
    accepted_by  uuid null references public.users(id),
    constraint project_invitations_pkey primary key (id),
    constraint project_invitations_token_key unique (token)
) TABLESPACE pg_default;

create index if not exists idx_project_invitations_token on public.project_invitations using btree (token) TABLESPACE pg_default;
create index if not exists idx_project_invitations_monument on public.project_invitations using btree (monument_id) TABLESPACE pg_default;
create index if not exists idx_project_invitations_email on public.project_invitations using btree (email) TABLESPACE pg_default;
-- Une seule invitation EN ATTENTE par (projet, email). Les invitations révoquées,
-- expirées ou acceptées n'empêchent pas l'envoi d'une nouvelle invitation.
create unique index if not exists project_invitations_unique_pending
    on public.project_invitations (monument_id, email) where status = 'pending';

-- 3. Type de compte + métier sur les utilisateurs
alter table public.users
    add column if not exists account_type text not null default 'proprietaire'
        check (account_type in ('proprietaire', 'collaborateur'));
alter table public.users
    add column if not exists metier text null;

-- 4. Backfill : chaque monument existant a son propriétaire comme membre 'owner'
insert into public.project_members (monument_id, user_id, role)
select m.id, m.user_id, 'owner'
from public.monuments m
on conflict (monument_id, user_id) do nothing;

-- 5. RLS : aucune policy permissive — accès volontairement réservé au service_role
--    (le backend bypass le RLS). Les clients anon/authenticated ne lisent pas ces tables.
alter table public.project_members enable row level security;
alter table public.project_invitations enable row level security;
