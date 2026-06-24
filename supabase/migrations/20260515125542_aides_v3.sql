create table if not exists public.aides_v3 (
    id uuid not null default gen_random_uuid (),
    nom text not null,
    description text not null,
    categorie text not null,
    type text not null,
    raison text[] not null,
    organisme text not null,
    montant_max numeric null,
    taux_max numeric null,
    montant_min numeric null,
    taux_min numeric null,
    commune_max_population integer null,
    conditions_eligibilite_detail text null,
    documents_requis jsonb null default '[]'::jsonb,
    date_ouverture date null,
    date_limite date null,
    permanent boolean not null default true,
    url_officielle text null,

    constraint aides_v3_categorie_check check (
        (
        categorie = any (
            array[
            'etat_drac'::text,
            'departement'::text,
            'fiscalite'::text,
            'europe'::text,
            'mecenat'::text,
            'fondation'::text,
            'region'::text,
            'autre'::text
            ]
        )
        )
    ),
    constraint aides_v3_type_check check (
        (
        type = any (
            array[
            'label'::text,
            'appel_a_projets'::text,
            'exoneration'::text,
            'mecenat'::text,
            'souscription'::text,
            'pret'::text,
            'deduction_fiscale'::text,
            'subvention'::text
            ]
        )
        )
    ),
    constraint aides_v3_raison_check check (
        raison <@ array[
            'etude_ingenierie',
            'restauration_travaux',
            'valorisation_rayonnement',
            'fiscalite'
        ]::text[]
    )
) TABLESPACE pg_default;
create index IF not exists idx_aides_v3_categorie on public.aides_v3 using btree (categorie) TABLESPACE pg_default;

create index IF not exists idx_aides_v3_permanent on public.aides_v3 using btree (permanent) TABLESPACE pg_default;

create index IF not exists idx_aides_v3_commune_pop on public.aides_v3 using btree (commune_max_population) 
