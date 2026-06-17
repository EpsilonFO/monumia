-- Bibliothèque de modèles (templates) de documents.
-- Table référentielle : modèles fournis par Monumia, rattachés aux pièces de
-- dossier par mots-clés côté applicatif (pas de FK vers les aides/dossiers).

create table if not exists public.templates (
    id uuid not null default gen_random_uuid (),
    slug text not null,
    nom text not null,
    description text null,
    type_document text not null,
    tags text[] not null default '{}'::text[],
    categories_aide text[] not null default '{}'::text[],
    organisme text null,
    fichier_url text not null,
    nom_fichier text not null,
    extension text null,
    mime_type text null,
    taille_fichier integer null,
    source_url text null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint templates_pkey primary key (id),
    constraint templates_slug_key unique (slug)
) TABLESPACE pg_default;

create index if not exists idx_templates_type on public.templates using btree (type_document) TABLESPACE pg_default;
create index if not exists idx_templates_tags on public.templates using gin (tags) TABLESPACE pg_default;
create index if not exists idx_templates_categories on public.templates using gin (categories_aide) TABLESPACE pg_default;

-- RLS : lecture pour les utilisateurs authentifiés, écritures réservées au
-- service_role (qui bypass RLS). Miroir d'aides_v3_rls.
alter table public.templates enable row level security;

drop policy if exists "templates_read" on public.templates;
create policy "templates_read"
    on public.templates
    as permissive
    for select
    to authenticated
    using (true);

-- Bucket de stockage des fichiers modèles. Public : ce sont des modèles
-- officiels, pas de données privées → URL publique directe, pas de signature.
insert into storage.buckets (id, name, public)
values ('templates', 'templates', true)
on conflict (id) do nothing;
