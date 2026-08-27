-- Équipe et documents au grain PROJET, à côté de ceux du monument.
--
-- Deux niveaux de partage cohabitent désormais :
--   * `project_members` (monument) — voit tout : la fiche, TOUS les projets,
--     les documents du monument et ceux de ses projets ;
--   * `projet_members` (ce fichier) — ne voit QUE son chantier : le projet, ses
--     aides, ses dossiers, ses documents, et la fiche sanitaire du monument en
--     lecture seule. Ni les autres projets, ni les documents du monument, ni
--     l'équipe du monument.
--
-- Le rôle effectif sur un projet est le MAXIMUM des deux appartenances : un
-- co_owner du monument reste co_owner de chacun de ses projets sans avoir de
-- ligne ici. D'où l'absence de 'owner' dans l'échelle : la propriété appartient
-- au monument, un projet n'a pas de propriétaire distinct.

create table public.projet_members (
    id         uuid not null default gen_random_uuid(),
    projet_id  uuid not null references public.projets (id) on delete cascade,
    user_id    uuid not null references public.users (id) on delete cascade,
    role       text not null check (role in ('co_owner', 'member')),
    invited_by uuid null references public.users (id),
    joined_at  timestamptz not null default now(),
    constraint projet_members_pkey primary key (id),
    constraint projet_members_unique unique (projet_id, user_id)
);

create index if not exists idx_projet_members_projet on public.projet_members using btree (projet_id);
create index if not exists idx_projet_members_user on public.projet_members using btree (user_id);

-- RLS : aucune policy permissive, comme project_members — le backend passe par
-- le service-role et tranche l'accès applicativement. Les clients anon /
-- authenticated ne lisent jamais cette table directement.
alter table public.projet_members enable row level security;

-- ---------------------------------------------------------------------------
-- Invitations : elles visent un monument, ou un projet précis de ce monument
-- ---------------------------------------------------------------------------

-- `monument_id` reste NOT NULL même pour une invitation de projet : c'est lui
-- qui nomme le bien dans l'e-mail et sur la page d'acceptation, et il évite une
-- jointure sur chaque aperçu public (route non authentifiée).
alter table public.project_invitations
    add column if not exists projet_id uuid null references public.projets (id) on delete cascade;

create index if not exists idx_project_invitations_projet
    on public.project_invitations using btree (projet_id);

-- Une seule invitation EN ATTENTE par (portée, email) : inviter quelqu'un sur
-- le monument et sur l'un de ses projets sont deux invitations distinctes, mais
-- deux fois la même portée n'a pas de sens. `coalesce` sur l'UUID nul parce
-- qu'un index unique laisserait passer les doublons de NULL.
drop index if exists public.project_invitations_unique_pending;
create unique index project_invitations_unique_pending
    on public.project_invitations (
        monument_id,
        coalesce(projet_id, '00000000-0000-0000-0000-000000000000'::uuid),
        email
    )
    where status = 'pending';

-- ---------------------------------------------------------------------------
-- Documents : rattachables au monument ET / OU à des projets
-- ---------------------------------------------------------------------------

-- `monument_ids` est CONSERVÉ : les pièces qui décrivent le bien (arrêté de
-- protection, cadastre, photos) servent tous les chantiers et n'ont pas à être
-- redéposées sur chacun. Un document peut porter les deux — déposé dans un
-- projet, il reste rattaché au monument pour l'équipe qui voit tout.
alter table public.documents
    add column if not exists projet_ids uuid[] not null default '{}'::uuid[];

create index if not exists idx_documents_projet_ids
    on public.documents using gin (projet_ids);
