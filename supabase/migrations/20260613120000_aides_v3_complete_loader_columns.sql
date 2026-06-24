-- Réaligne aides_v3 sur le schéma attendu par le loader (load_aides_yaml.py /
-- aides_schema.Aide) et par le routeur (routers/aides.py).
--
-- Contexte : pendant la refonte, aides_v3 a été recréée à la main avec un schéma
-- « slim » (id, nom, raison, taux_min, … + slug/verified_at). Cette recréation
-- hors-migration a fait disparaître :
--   • les colonnes riches posées par 20260405170500_remote_schema
--     (nom_court, description_longue, plancher, base_ttc, flags, …) ;
--   • les colonnes tableau posées par 20260528203714_consolidate
--     (protections, proprietaires, travaux, regions, departements,
--      etats_conservation) et leurs index GIN.
-- Sans elles, l'insert du loader échoue (PGRST204 « Could not find the
-- 'architecte_requis' column … »).
--
-- Toutes les colonnes/index sont ajoutés en IF NOT EXISTS : no-op sur une base
-- déjà complète, réparation sur une base ayant subi la dérive.

alter table public.aides_v3
    add column if not exists nom_court             text,
    add column if not exists description_longue    text,
    add column if not exists formulaire_url        text,
    add column if not exists demarche_description  text,
    add column if not exists delai_instruction     text,
    add column if not exists plancher              numeric,
    add column if not exists base_ttc              boolean not null default false,
    add column if not exists architecte_requis     boolean not null default false,
    add column if not exists cofinancement_requis  boolean not null default false,
    add column if not exists tags                  jsonb   default '[]'::jsonb,
    add column if not exists protections           text[]  not null default '{}'::text[],
    add column if not exists proprietaires         text[]  not null default '{}'::text[],
    add column if not exists travaux               text[]  not null default '{}'::text[],
    add column if not exists regions               text[]  not null default '{}'::text[],
    add column if not exists departements          text[]  not null default '{}'::text[],
    add column if not exists etats_conservation    text[]  not null default '{}'::text[];

-- Index GIN pour les prédicats && / = ANY() du pré-filtre (cf. 20260528203714).
create index if not exists idx_aides_v3_protections        on public.aides_v3 using gin (protections);
create index if not exists idx_aides_v3_proprietaires      on public.aides_v3 using gin (proprietaires);
create index if not exists idx_aides_v3_travaux            on public.aides_v3 using gin (travaux);
create index if not exists idx_aides_v3_regions            on public.aides_v3 using gin (regions);
create index if not exists idx_aides_v3_departements       on public.aides_v3 using gin (departements);
create index if not exists idx_aides_v3_etats_conservation on public.aides_v3 using gin (etats_conservation);
