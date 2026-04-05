create extension if not exists "wrappers" with schema "extensions";

drop extension if exists "pg_net";

create schema if not exists "vecs";

create extension if not exists "unaccent" with schema "public";

create extension if not exists "vector" with schema "public";

create type "public"."aide_category" as enum ('etat_drac', 'region', 'departement', 'fondation_patrimoine', 'europe', 'mecenat', 'fiscalite', 'autre');

create type "public"."aide_type" as enum ('subvention', 'avance', 'pret', 'deduction_fiscale', 'label', 'mecenat', 'souscription', 'autre');

create type "public"."document_type" as enum ('photo', 'plan', 'devis', 'facture', 'attestation', 'extrait_cadastral', 'cerfa', 'arrete', 'diagnostic', 'rapport', 'correspondance', 'autre');

create type "public"."dossier_status" as enum ('brouillon', 'en_cours', 'complet', 'pret', 'soumis');

create type "public"."etat_conservation" as enum ('bon', 'moyen', 'mauvais', 'peril');

create type "public"."notification_category" as enum ('deadline_proche', 'nouvelle_aide', 'dossier_update', 'document_manquant', 'collaborateur', 'system');

create type "public"."notification_type" as enum ('urgent', 'opportunite', 'info');

create type "public"."ownership_type" as enum ('public_commune', 'public_departement', 'public_region', 'public_etat', 'prive_personne_physique', 'prive_sci', 'association', 'mixte');

create type "public"."prospect_priorite" as enum ('haute', 'moyenne', 'basse');

create type "public"."prospect_status" as enum ('a_contacter', 'contacte', 'en_discussion', 'devis_envoye', 'gagne', 'perdu');

create type "public"."protection_level" as enum ('classe', 'inscrit', 'abords', 'spr', 'non_protege');

create type "public"."urgence_travaux" as enum ('faible', 'moyenne', 'haute', 'critique');

create type "public"."user_segment" as enum ('commune', 'prive', 'btp');


  create table "public"."aides_departements" (
    "aide_id" uuid not null,
    "departement_code" text not null
      );


alter table "public"."aides_departements" enable row level security;


  create table "public"."aides_etats_conservation" (
    "aide_id" uuid not null,
    "etat_conservation_code" text not null
      );


alter table "public"."aides_etats_conservation" enable row level security;


  create table "public"."aides_proprietaires" (
    "aide_id" uuid not null,
    "proprietaire_code" text not null
      );


alter table "public"."aides_proprietaires" enable row level security;


  create table "public"."aides_protections" (
    "aide_id" uuid not null,
    "protection_code" text not null
      );


alter table "public"."aides_protections" enable row level security;


  create table "public"."aides_regions" (
    "aide_id" uuid not null,
    "region_code" text not null
      );


alter table "public"."aides_regions" enable row level security;


  create table "public"."aides_segments" (
    "aide_id" uuid not null,
    "segment_code" text not null
      );


alter table "public"."aides_segments" enable row level security;


  create table "public"."aides_travaux" (
    "aide_id" uuid not null,
    "travaux_code" text not null
      );


alter table "public"."aides_travaux" enable row level security;


  create table "public"."aides_v2" (
    "id" uuid not null default gen_random_uuid(),
    "nom" text not null,
    "nom_court" text not null,
    "description" text not null,
    "description_longue" text,
    "categorie" text not null,
    "type" text not null,
    "organisme" text not null,
    "montant_max" numeric,
    "taux_max" numeric,
    "montant_min" numeric,
    "plancher" numeric,
    "base_ttc" boolean not null default false,
    "commune_max_population" integer,
    "cofinancement_requis" boolean not null default false,
    "architecte_requis" boolean not null default false,
    "conditions_eligibilite_detail" text,
    "demarche_description" text,
    "documents_requis" jsonb default '[]'::jsonb,
    "delai_instruction" text,
    "date_ouverture" date,
    "date_limite" date,
    "permanent" boolean not null default true,
    "url_officielle" text,
    "formulaire_url" text,
    "tags" jsonb default '[]'::jsonb,
    "created_at" timestamp with time zone not null default now(),
    "updated_at" timestamp with time zone not null default now()
      );


alter table "public"."aides_v2" enable row level security;


  create table "public"."communes" (
    "code_insee" text not null,
    "nom_commune" text not null,
    "departement" text not null,
    "departement_num" text not null,
    "region" text not null,
    "arrondissement" text,
    "population" integer,
    "nom_commune_matching" text
      );


alter table "public"."communes" enable row level security;


  create table "public"."diagnostics" (
    "id" uuid not null default gen_random_uuid(),
    "monument_id" uuid not null,
    "user_id" uuid not null,
    "mode_projet" boolean not null default false,
    "travaux_filtres" jsonb,
    "total_aides_analysees" integer not null,
    "aides_eligibles_count" integer not null,
    "aides_non_eligibles_count" integer not null,
    "montant_potentiel_total" numeric,
    "aides_eligibles_ids" uuid[] not null default '{}'::uuid[],
    "aides_non_eligibles_ids" uuid[] not null default '{}'::uuid[],
    "created_at" timestamp with time zone not null default now(),
    "aides_potentiellement_eligibles_count" integer default 0,
    "aides_potentiellement_eligibles_ids" uuid[] default '{}'::uuid[]
      );


alter table "public"."diagnostics" enable row level security;


  create table "public"."documents" (
    "id" uuid not null default gen_random_uuid(),
    "user_id" uuid not null,
    "nom" text not null,
    "nom_fichier" text not null,
    "type" public.document_type not null,
    "tags" text[] not null default '{}'::text[],
    "taille_fichier" bigint not null,
    "mime_type" text not null,
    "url" text not null,
    "dossiers_utilises" uuid[] not null default '{}'::uuid[],
    "date_upload" timestamp with time zone not null default now(),
    "date_document" date,
    "description" text,
    "monument_ids" text[] default '{}'::text[]
      );


alter table "public"."documents" enable row level security;


  create table "public"."dossiers" (
    "id" uuid not null default gen_random_uuid(),
    "user_id" uuid not null,
    "monument_id" uuid not null,
    "aide_id" text not null,
    "titre" text not null,
    "description" text,
    "etape_actuelle" integer not null default 1,
    "statut" public.dossier_status not null default 'brouillon'::public.dossier_status,
    "progression_pourcentage" integer not null default 0,
    "travaux_prevus" text[] not null default '{}'::text[],
    "montant_estime" numeric,
    "checklist" jsonb not null default '[]'::jsonb,
    "sections" jsonb not null default '[]'::jsonb,
    "echeances" jsonb not null default '[]'::jsonb,
    "collaborateurs" jsonb not null default '[]'::jsonb,
    "date_creation" timestamp with time zone not null default now(),
    "date_derniere_modification" timestamp with time zone not null default now(),
    "date_soumission" timestamp with time zone
      );


alter table "public"."dossiers" enable row level security;


  create table "public"."merimee_buildings" (
    "reference" text not null,
    "region" text,
    "domaine" text,
    "lieudit" text,
    "remploi" text,
    "cadastre" text,
    "copyright" text,
    "historique" text,
    "producteur" text,
    "observations" text,
    "date_de_label" text,
    "liens_externes" text,
    "cadre_de_l_etude" text,
    "nom_du_redacteur" text,
    "typologie_de_plan" text,
    "type_de_couverture" text,
    "adresse_forme_index" text,
    "auteur_de_l_edifice" text,
    "commune_forme_index" text,
    "identifiant_agregee" text,
    "partie_constituante" text,
    "typologie_du_dossier" text,
    "etat_de_conservation" text,
    "datation_de_l_edifice" text,
    "genre_du_destinataire" text,
    "departement_en_lettres" text,
    "precision_affectataire" text,
    "nature_de_la_protection" text,
    "reference_a_un_ensemble" text,
    "typologie_du_couvrement" text,
    "adresse_forme_editoriale" text,
    "commune_forme_editoriale" text,
    "description_de_l_edifice" text,
    "materiaux_du_gros_oeuvre" text,
    "denomination_de_l_edifice" text,
    "justification_attribution" text,
    "lien_vers_la_base_joconde" text,
    "lien_vers_la_base_palissy" text,
    "materiaux_de_la_couverture" text,
    "precision_de_la_protection" text,
    "typologie_de_la_protection" text,
    "lien_vers_la_base_archiv_mh" text,
    "personnes_liees_a_l_edifice" text,
    "coordonnees_au_format_wgs84" text,
    "departement_format_numerique" text,
    "justification_de_la_datation" text,
    "precision_de_la_localisation" text,
    "titre_editorial_de_la_notice" text,
    "date_de_creation_de_la_notice" text,
    "description_de_l_iconographie" text,
    "partie_d_elevation_exterieure" text,
    "precision_sur_la_denomination" text,
    "statut_juridique_de_l_edifice" text,
    "autre_appellation_de_l_edifice" text,
    "cog_insee_lors_de_la_protection" text,
    "date_de_la_derniere_mise_a_jour" text,
    "partie_constituante_non_etudiee" text,
    "destination_actuelle_de_l_edifice" text,
    "date_et_typologie_de_la_protection" text,
    "typologie_de_la_zone_de_protection" text,
    "elements_remarquables_dans_l_edifice" text,
    "indexation_iconographique_normalisee" text,
    "precision_sur_le_statut_de_l_edifice" text,
    "vocable___pour_les_edifices_cultuels" text,
    "description_de_l_elevation_interieure" text,
    "technique_du_decor_porte_de_l_edifice" text,
    "etablissement_affectataire_de_l_edifice" text,
    "format_abrege_du_siecle_de_construction" text,
    "source_de_l_energie_utilisee_par_l_edifice" text,
    "couverts_ou_decouverts_du_jardin_de_l_edifice" text,
    "emplacement__forme_et_structure_de_l_escalier" text,
    "references_des_parties_constituantes_etudiees" text,
    "siecle_de_campagne_secondaire_de_construction" text,
    "dimensions_normalisees_des_edicules_uniquement" text,
    "siecle_de_la_campagne_principale_de_construction" text,
    "nom_du_cours_d_eau_traversant_ou_bordant_l_edifice" text,
    "renvoi_vers_une_notice_de_la_base_merimee_ou_palissy" text,
    "lieu_de_conservation_d_un_element_architectural_deplace" text
      );


alter table "public"."merimee_buildings" enable row level security;


  create table "public"."monuments" (
    "id" uuid not null default gen_random_uuid(),
    "user_id" uuid not null,
    "nom" text not null,
    "denomination" text not null,
    "code_insee" text,
    "reference_merimee" text,
    "protection" public.protection_level not null,
    "date_protection" date,
    "type_protection" text,
    "proprietaire" public.ownership_type not null,
    "affectataire" text,
    "siecle_construction" text,
    "periode_construction" text[],
    "superficie" numeric,
    "materiaux" text[],
    "type_couverture" text,
    "nombre_niveaux" integer,
    "description_generale" text,
    "etat_conservation" public.etat_conservation not null,
    "travaux_envisages" text[],
    "urgence_travaux" public.urgence_travaux,
    "diagnostic_realise" boolean default false,
    "derniers_travaux" date,
    "description_etat" text,
    "photos" jsonb not null default '[]'::jsonb,
    "completion_percentage" integer not null default 0,
    "created_at" timestamp with time zone not null default now(),
    "updated_at" timestamp with time zone not null default now()
      );


alter table "public"."monuments" enable row level security;


  create table "public"."notifications" (
    "id" uuid not null default gen_random_uuid(),
    "user_id" uuid not null,
    "type" public.notification_type not null,
    "categorie" public.notification_category not null,
    "titre" text not null,
    "message" text not null,
    "lue" boolean not null default false,
    "lien_vers" jsonb,
    "date_creation" timestamp with time zone not null default now()
      );


alter table "public"."notifications" enable row level security;


  create table "public"."prospects" (
    "id" uuid not null default gen_random_uuid(),
    "btp_user_id" uuid not null,
    "proprietaire" text,
    "travaux_envisages" text[],
    "description_etat" text,
    "etat_conservation" text,
    "contact_nom" text,
    "contact_email" text,
    "contact_telephone" text,
    "contact_fonction" text,
    "statut" public.prospect_status not null default 'a_contacter'::public.prospect_status,
    "priorite" public.prospect_priorite not null default 'moyenne'::public.prospect_priorite,
    "date_prochain_contact" date,
    "notes" text,
    "financement_identifie" boolean not null default false,
    "aides_matchees" text[],
    "total_financement_potentiel" numeric,
    "taux_couverture_estime" numeric,
    "montant_travaux" numeric,
    "created_at" timestamp with time zone not null default now(),
    "updated_at" timestamp with time zone not null default now(),
    "monument_id" uuid not null
      );


alter table "public"."prospects" enable row level security;


  create table "public"."ref_etats_conservation" (
    "code" text not null,
    "label" text not null
      );


alter table "public"."ref_etats_conservation" enable row level security;


  create table "public"."ref_proprietaires" (
    "code" text not null,
    "label" text not null
      );


alter table "public"."ref_proprietaires" enable row level security;


  create table "public"."ref_protections" (
    "code" text not null,
    "label" text not null
      );


alter table "public"."ref_protections" enable row level security;


  create table "public"."ref_segments" (
    "code" text not null,
    "label" text not null
      );


alter table "public"."ref_segments" enable row level security;


  create table "public"."ref_travaux" (
    "code" text not null,
    "label" text not null
      );


alter table "public"."ref_travaux" enable row level security;


  create table "public"."users" (
    "id" uuid not null,
    "email" text not null,
    "prenom" text not null,
    "nom" text not null,
    "segment" public.user_segment not null,
    "telephone" text,
    "btp" jsonb,
    "onboarding_complete" boolean not null default false,
    "notification_preferences" jsonb not null default '{"dossierUpdates": true, "newAidesMatched": true, "urgentDeadlines": true, "emailNotifications": false}'::jsonb,
    "created_at" timestamp with time zone not null default now(),
    "updated_at" timestamp with time zone not null default now(),
    "commune_code_insee" text,
    "commune_fonction" text,
    "prive_type_proprietaire" text,
    "prive_regime_fiscal" text
      );


alter table "public"."users" enable row level security;


  create table "vecs"."document_chunks" (
    "id" character varying not null,
    "vec" public.vector(1024) not null,
    "metadata" jsonb not null default '{}'::jsonb
      );


CREATE UNIQUE INDEX aides_departements_pkey ON public.aides_departements USING btree (aide_id, departement_code);

CREATE UNIQUE INDEX aides_etats_conservation_pkey ON public.aides_etats_conservation USING btree (aide_id, etat_conservation_code);

CREATE UNIQUE INDEX aides_proprietaires_pkey ON public.aides_proprietaires USING btree (aide_id, proprietaire_code);

CREATE UNIQUE INDEX aides_protections_pkey ON public.aides_protections USING btree (aide_id, protection_code);

CREATE UNIQUE INDEX aides_regions_pkey ON public.aides_regions USING btree (aide_id, region_code);

CREATE UNIQUE INDEX aides_segments_pkey ON public.aides_segments USING btree (aide_id, segment_code);

CREATE UNIQUE INDEX aides_travaux_pkey ON public.aides_travaux USING btree (aide_id, travaux_code);

CREATE UNIQUE INDEX aides_v2_pkey ON public.aides_v2 USING btree (id);

CREATE UNIQUE INDEX communes_pkey ON public.communes USING btree (code_insee);

CREATE UNIQUE INDEX diagnostics_pkey ON public.diagnostics USING btree (id);

CREATE UNIQUE INDEX documents_pkey ON public.documents USING btree (id);

CREATE INDEX documents_user_id_idx ON public.documents USING btree (user_id);

CREATE INDEX dossiers_monument_id_idx ON public.dossiers USING btree (monument_id);

CREATE UNIQUE INDEX dossiers_pkey ON public.dossiers USING btree (id);

CREATE INDEX dossiers_statut_idx ON public.dossiers USING btree (statut);

CREATE INDEX dossiers_user_id_idx ON public.dossiers USING btree (user_id);

CREATE INDEX idx_aides_departements_code ON public.aides_departements USING btree (departement_code);

CREATE INDEX idx_aides_etats_code ON public.aides_etats_conservation USING btree (etat_conservation_code);

CREATE INDEX idx_aides_proprietaires_code ON public.aides_proprietaires USING btree (proprietaire_code);

CREATE INDEX idx_aides_protections_code ON public.aides_protections USING btree (protection_code);

CREATE INDEX idx_aides_regions_code ON public.aides_regions USING btree (region_code);

CREATE INDEX idx_aides_segments_code ON public.aides_segments USING btree (segment_code);

CREATE INDEX idx_aides_travaux_code ON public.aides_travaux USING btree (travaux_code);

CREATE INDEX idx_aides_v2_categorie ON public.aides_v2 USING btree (categorie);

CREATE INDEX idx_aides_v2_commune_pop ON public.aides_v2 USING btree (commune_max_population);

CREATE INDEX idx_aides_v2_permanent ON public.aides_v2 USING btree (permanent);

CREATE INDEX idx_diagnostics_monument_id ON public.diagnostics USING btree (monument_id);

CREATE INDEX idx_diagnostics_user_id ON public.diagnostics USING btree (user_id);

CREATE INDEX idx_prospects_btp_user_id ON public.prospects USING btree (btp_user_id);

CREATE INDEX idx_prospects_statut ON public.prospects USING btree (statut);

CREATE UNIQUE INDEX merimee_buildings_pkey ON public.merimee_buildings USING btree (reference);

CREATE UNIQUE INDEX monuments_pkey ON public.monuments USING btree (id);

CREATE INDEX monuments_reference_merimee_idx ON public.monuments USING btree (reference_merimee);

CREATE INDEX monuments_user_id_idx ON public.monuments USING btree (user_id);

CREATE UNIQUE INDEX notifications_pkey ON public.notifications USING btree (id);

CREATE INDEX notifications_user_id_idx ON public.notifications USING btree (user_id);

CREATE INDEX notifications_user_lue_idx ON public.notifications USING btree (user_id, lue);

CREATE UNIQUE INDEX prospects_pkey ON public.prospects USING btree (id);

CREATE UNIQUE INDEX ref_etats_conservation_pkey ON public.ref_etats_conservation USING btree (code);

CREATE UNIQUE INDEX ref_proprietaires_pkey ON public.ref_proprietaires USING btree (code);

CREATE UNIQUE INDEX ref_protections_pkey ON public.ref_protections USING btree (code);

CREATE UNIQUE INDEX ref_segments_pkey ON public.ref_segments USING btree (code);

CREATE UNIQUE INDEX ref_travaux_pkey ON public.ref_travaux USING btree (code);

CREATE UNIQUE INDEX users_pkey ON public.users USING btree (id);

CREATE UNIQUE INDEX document_chunks_pkey ON vecs.document_chunks USING btree (id);

CREATE INDEX ix_vector_cosine_ops_hnsw_m16_efc64_c048cdc ON vecs.document_chunks USING hnsw (vec public.vector_cosine_ops) WITH (m='16', ef_construction='64');

alter table "public"."aides_departements" add constraint "aides_departements_pkey" PRIMARY KEY using index "aides_departements_pkey";

alter table "public"."aides_etats_conservation" add constraint "aides_etats_conservation_pkey" PRIMARY KEY using index "aides_etats_conservation_pkey";

alter table "public"."aides_proprietaires" add constraint "aides_proprietaires_pkey" PRIMARY KEY using index "aides_proprietaires_pkey";

alter table "public"."aides_protections" add constraint "aides_protections_pkey" PRIMARY KEY using index "aides_protections_pkey";

alter table "public"."aides_regions" add constraint "aides_regions_pkey" PRIMARY KEY using index "aides_regions_pkey";

alter table "public"."aides_segments" add constraint "aides_segments_pkey" PRIMARY KEY using index "aides_segments_pkey";

alter table "public"."aides_travaux" add constraint "aides_travaux_pkey" PRIMARY KEY using index "aides_travaux_pkey";

alter table "public"."aides_v2" add constraint "aides_v2_pkey" PRIMARY KEY using index "aides_v2_pkey";

alter table "public"."communes" add constraint "communes_pkey" PRIMARY KEY using index "communes_pkey";

alter table "public"."diagnostics" add constraint "diagnostics_pkey" PRIMARY KEY using index "diagnostics_pkey";

alter table "public"."documents" add constraint "documents_pkey" PRIMARY KEY using index "documents_pkey";

alter table "public"."dossiers" add constraint "dossiers_pkey" PRIMARY KEY using index "dossiers_pkey";

alter table "public"."merimee_buildings" add constraint "merimee_buildings_pkey" PRIMARY KEY using index "merimee_buildings_pkey";

alter table "public"."monuments" add constraint "monuments_pkey" PRIMARY KEY using index "monuments_pkey";

alter table "public"."notifications" add constraint "notifications_pkey" PRIMARY KEY using index "notifications_pkey";

alter table "public"."prospects" add constraint "prospects_pkey" PRIMARY KEY using index "prospects_pkey";

alter table "public"."ref_etats_conservation" add constraint "ref_etats_conservation_pkey" PRIMARY KEY using index "ref_etats_conservation_pkey";

alter table "public"."ref_proprietaires" add constraint "ref_proprietaires_pkey" PRIMARY KEY using index "ref_proprietaires_pkey";

alter table "public"."ref_protections" add constraint "ref_protections_pkey" PRIMARY KEY using index "ref_protections_pkey";

alter table "public"."ref_segments" add constraint "ref_segments_pkey" PRIMARY KEY using index "ref_segments_pkey";

alter table "public"."ref_travaux" add constraint "ref_travaux_pkey" PRIMARY KEY using index "ref_travaux_pkey";

alter table "public"."users" add constraint "users_pkey" PRIMARY KEY using index "users_pkey";

alter table "vecs"."document_chunks" add constraint "document_chunks_pkey" PRIMARY KEY using index "document_chunks_pkey";

alter table "public"."aides_departements" add constraint "aides_departements_aide_id_fkey" FOREIGN KEY (aide_id) REFERENCES public.aides_v2(id) ON DELETE CASCADE not valid;

alter table "public"."aides_departements" validate constraint "aides_departements_aide_id_fkey";

alter table "public"."aides_etats_conservation" add constraint "aides_etats_conservation_aide_id_fkey" FOREIGN KEY (aide_id) REFERENCES public.aides_v2(id) ON DELETE CASCADE not valid;

alter table "public"."aides_etats_conservation" validate constraint "aides_etats_conservation_aide_id_fkey";

alter table "public"."aides_etats_conservation" add constraint "aides_etats_conservation_etat_conservation_code_fkey" FOREIGN KEY (etat_conservation_code) REFERENCES public.ref_etats_conservation(code) not valid;

alter table "public"."aides_etats_conservation" validate constraint "aides_etats_conservation_etat_conservation_code_fkey";

alter table "public"."aides_proprietaires" add constraint "aides_proprietaires_aide_id_fkey" FOREIGN KEY (aide_id) REFERENCES public.aides_v2(id) ON DELETE CASCADE not valid;

alter table "public"."aides_proprietaires" validate constraint "aides_proprietaires_aide_id_fkey";

alter table "public"."aides_proprietaires" add constraint "aides_proprietaires_proprietaire_code_fkey" FOREIGN KEY (proprietaire_code) REFERENCES public.ref_proprietaires(code) not valid;

alter table "public"."aides_proprietaires" validate constraint "aides_proprietaires_proprietaire_code_fkey";

alter table "public"."aides_protections" add constraint "aides_protections_aide_id_fkey" FOREIGN KEY (aide_id) REFERENCES public.aides_v2(id) ON DELETE CASCADE not valid;

alter table "public"."aides_protections" validate constraint "aides_protections_aide_id_fkey";

alter table "public"."aides_protections" add constraint "aides_protections_protection_code_fkey" FOREIGN KEY (protection_code) REFERENCES public.ref_protections(code) not valid;

alter table "public"."aides_protections" validate constraint "aides_protections_protection_code_fkey";

alter table "public"."aides_regions" add constraint "aides_regions_aide_id_fkey" FOREIGN KEY (aide_id) REFERENCES public.aides_v2(id) ON DELETE CASCADE not valid;

alter table "public"."aides_regions" validate constraint "aides_regions_aide_id_fkey";

alter table "public"."aides_segments" add constraint "aides_segments_aide_id_fkey" FOREIGN KEY (aide_id) REFERENCES public.aides_v2(id) ON DELETE CASCADE not valid;

alter table "public"."aides_segments" validate constraint "aides_segments_aide_id_fkey";

alter table "public"."aides_segments" add constraint "aides_segments_segment_code_fkey" FOREIGN KEY (segment_code) REFERENCES public.ref_segments(code) not valid;

alter table "public"."aides_segments" validate constraint "aides_segments_segment_code_fkey";

alter table "public"."aides_travaux" add constraint "aides_travaux_aide_id_fkey" FOREIGN KEY (aide_id) REFERENCES public.aides_v2(id) ON DELETE CASCADE not valid;

alter table "public"."aides_travaux" validate constraint "aides_travaux_aide_id_fkey";

alter table "public"."aides_travaux" add constraint "aides_travaux_travaux_code_fkey" FOREIGN KEY (travaux_code) REFERENCES public.ref_travaux(code) not valid;

alter table "public"."aides_travaux" validate constraint "aides_travaux_travaux_code_fkey";

alter table "public"."diagnostics" add constraint "diagnostics_monument_id_fkey" FOREIGN KEY (monument_id) REFERENCES public.monuments(id) ON DELETE CASCADE not valid;

alter table "public"."diagnostics" validate constraint "diagnostics_monument_id_fkey";

alter table "public"."diagnostics" add constraint "diagnostics_user_id_fkey" FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE not valid;

alter table "public"."diagnostics" validate constraint "diagnostics_user_id_fkey";

alter table "public"."documents" add constraint "documents_user_id_fkey" FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE not valid;

alter table "public"."documents" validate constraint "documents_user_id_fkey";

alter table "public"."dossiers" add constraint "dossiers_etape_actuelle_check" CHECK (((etape_actuelle >= 1) AND (etape_actuelle <= 5))) not valid;

alter table "public"."dossiers" validate constraint "dossiers_etape_actuelle_check";

alter table "public"."dossiers" add constraint "dossiers_monument_id_fkey" FOREIGN KEY (monument_id) REFERENCES public.monuments(id) ON DELETE CASCADE not valid;

alter table "public"."dossiers" validate constraint "dossiers_monument_id_fkey";

alter table "public"."dossiers" add constraint "dossiers_progression_pourcentage_check" CHECK (((progression_pourcentage >= 0) AND (progression_pourcentage <= 100))) not valid;

alter table "public"."dossiers" validate constraint "dossiers_progression_pourcentage_check";

alter table "public"."dossiers" add constraint "dossiers_user_id_fkey" FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE not valid;

alter table "public"."dossiers" validate constraint "dossiers_user_id_fkey";

alter table "public"."monuments" add constraint "monuments_user_id_fkey" FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE not valid;

alter table "public"."monuments" validate constraint "monuments_user_id_fkey";

alter table "public"."notifications" add constraint "notifications_user_id_fkey" FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE not valid;

alter table "public"."notifications" validate constraint "notifications_user_id_fkey";

alter table "public"."prospects" add constraint "prospects_btp_user_id_fkey" FOREIGN KEY (btp_user_id) REFERENCES auth.users(id) ON DELETE CASCADE not valid;

alter table "public"."prospects" validate constraint "prospects_btp_user_id_fkey";

alter table "public"."prospects" add constraint "prospects_monument_id_fkey" FOREIGN KEY (monument_id) REFERENCES public.monuments(id) ON DELETE CASCADE not valid;

alter table "public"."prospects" validate constraint "prospects_monument_id_fkey";

alter table "public"."prospects" add constraint "prospects_taux_couverture_estime_check" CHECK (((taux_couverture_estime >= (0)::numeric) AND (taux_couverture_estime <= (100)::numeric))) not valid;

alter table "public"."prospects" validate constraint "prospects_taux_couverture_estime_check";

alter table "public"."users" add constraint "fk_users_commune" FOREIGN KEY (commune_code_insee) REFERENCES public.communes(code_insee) not valid;

alter table "public"."users" validate constraint "fk_users_commune";

alter table "public"."users" add constraint "users_id_fkey" FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE not valid;

alter table "public"."users" validate constraint "users_id_fkey";

set check_function_bodies = off;

CREATE OR REPLACE FUNCTION public.match_document_chunks(query_embedding public.vector, match_count integer DEFAULT 5)
 RETURNS TABLE(chunk_id uuid, document_id uuid, filename text, content text, similarity double precision)
 LANGUAGE sql
 STABLE
AS $function$
  select
    chunk_id,
    document_id,
    filename,
    content,
    1 - (embedding <=> query_embedding) as similarity
  from document_chunks
  order by embedding <=> query_embedding
  limit match_count;
$function$
;

CREATE OR REPLACE FUNCTION public.prefiltrer_aides(p_protection text DEFAULT NULL::text, p_proprietaire text DEFAULT NULL::text, p_travaux text[] DEFAULT NULL::text[], p_region text DEFAULT NULL::text, p_departement text DEFAULT NULL::text, p_segment text DEFAULT NULL::text, p_population integer DEFAULT NULL::integer, p_etat_conservation text DEFAULT NULL::text)
 RETURNS TABLE(aide_id uuid)
 LANGUAGE sql
 STABLE
AS $function$
  SELECT DISTINCT a.id
  FROM aides_v2 a
  WHERE
    -- Protection : paramètre NULL = pas de filtre, sinon l'aide n'a aucune contrainte OU le monument matche
    (p_protection IS NULL
     OR NOT EXISTS (SELECT 1 FROM aides_protections ap WHERE ap.aide_id = a.id)
     OR EXISTS (SELECT 1 FROM aides_protections ap WHERE ap.aide_id = a.id AND ap.protection_code = p_protection))

    -- Propriétaire
    AND (p_proprietaire IS NULL
     OR NOT EXISTS (SELECT 1 FROM aides_proprietaires ap WHERE ap.aide_id = a.id)
     OR EXISTS (SELECT 1 FROM aides_proprietaires ap WHERE ap.aide_id = a.id AND ap.proprietaire_code = p_proprietaire))

    -- Travaux : paramètre NULL = pas de filtre, sinon au moins un en commun
    AND (p_travaux IS NULL
     OR NOT EXISTS (SELECT 1 FROM aides_travaux at2 WHERE at2.aide_id = a.id)
     OR EXISTS (SELECT 1 FROM aides_travaux at2 WHERE at2.aide_id = a.id AND at2.travaux_code = ANY(p_travaux)))

    -- Région
    AND (p_region IS NULL
     OR NOT EXISTS (SELECT 1 FROM aides_regions ar WHERE ar.aide_id = a.id)
     OR EXISTS (SELECT 1 FROM aides_regions ar WHERE ar.aide_id = a.id AND ar.region_code = p_region))

    -- Département
    AND (p_departement IS NULL
     OR NOT EXISTS (SELECT 1 FROM aides_departements ad WHERE ad.aide_id = a.id)
     OR EXISTS (SELECT 1 FROM aides_departements ad WHERE ad.aide_id = a.id AND ad.departement_code = p_departement))

    -- Segment
    AND (p_segment IS NULL
     OR NOT EXISTS (SELECT 1 FROM aides_segments as2 WHERE as2.aide_id = a.id)
     OR EXISTS (SELECT 1 FROM aides_segments as2 WHERE as2.aide_id = a.id AND as2.segment_code = p_segment))

    -- Population
    AND (a.commune_max_population IS NULL OR p_population IS NULL OR p_population <= a.commune_max_population)

    -- État de conservation
    AND (p_etat_conservation IS NULL
     OR NOT EXISTS (SELECT 1 FROM aides_etats_conservation ae WHERE ae.aide_id = a.id)
     OR EXISTS (SELECT 1 FROM aides_etats_conservation ae WHERE ae.aide_id = a.id AND ae.etat_conservation_code = p_etat_conservation))

    -- Pas expirée
    AND (a.permanent = true OR a.date_limite IS NULL OR a.date_limite >= CURRENT_DATE)
  ;
$function$
;

CREATE OR REPLACE FUNCTION public.search_merimee(tokens text[])
 RETURNS TABLE(reference text, region text, commune_forme_index text, departement_en_lettres text, typologie_de_la_protection text, titre_editorial_de_la_notice text)
 LANGUAGE sql
 STABLE
AS $function$
  select
    reference,
    region,
    commune_forme_index,
    departement_en_lettres,
    typologie_de_la_protection,
    titre_editorial_de_la_notice
  from merimee_buildings
  where (
    select bool_and(
      unaccent(
        coalesce(titre_editorial_de_la_notice, '') || ' ' ||
        coalesce(commune_forme_index, '')           || ' ' ||
        coalesce(departement_en_lettres, '')        || ' ' ||
        coalesce(region, '')                        || ' ' ||
        coalesce(reference, '')                     || ' ' ||
        coalesce(typologie_de_la_protection, '')
      ) ilike '%' || unaccent(t) || '%'
    )
    from unnest(tokens) t
  );
$function$
;

CREATE OR REPLACE FUNCTION public.update_dossier_modification()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
begin
  new.date_derniere_modification = now();
  return new;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.update_updated_at()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$function$
;

grant delete on table "public"."aides_departements" to "anon";

grant insert on table "public"."aides_departements" to "anon";

grant references on table "public"."aides_departements" to "anon";

grant select on table "public"."aides_departements" to "anon";

grant trigger on table "public"."aides_departements" to "anon";

grant truncate on table "public"."aides_departements" to "anon";

grant update on table "public"."aides_departements" to "anon";

grant delete on table "public"."aides_departements" to "authenticated";

grant insert on table "public"."aides_departements" to "authenticated";

grant references on table "public"."aides_departements" to "authenticated";

grant select on table "public"."aides_departements" to "authenticated";

grant trigger on table "public"."aides_departements" to "authenticated";

grant truncate on table "public"."aides_departements" to "authenticated";

grant update on table "public"."aides_departements" to "authenticated";

grant delete on table "public"."aides_departements" to "service_role";

grant insert on table "public"."aides_departements" to "service_role";

grant references on table "public"."aides_departements" to "service_role";

grant select on table "public"."aides_departements" to "service_role";

grant trigger on table "public"."aides_departements" to "service_role";

grant truncate on table "public"."aides_departements" to "service_role";

grant update on table "public"."aides_departements" to "service_role";

grant delete on table "public"."aides_etats_conservation" to "anon";

grant insert on table "public"."aides_etats_conservation" to "anon";

grant references on table "public"."aides_etats_conservation" to "anon";

grant select on table "public"."aides_etats_conservation" to "anon";

grant trigger on table "public"."aides_etats_conservation" to "anon";

grant truncate on table "public"."aides_etats_conservation" to "anon";

grant update on table "public"."aides_etats_conservation" to "anon";

grant delete on table "public"."aides_etats_conservation" to "authenticated";

grant insert on table "public"."aides_etats_conservation" to "authenticated";

grant references on table "public"."aides_etats_conservation" to "authenticated";

grant select on table "public"."aides_etats_conservation" to "authenticated";

grant trigger on table "public"."aides_etats_conservation" to "authenticated";

grant truncate on table "public"."aides_etats_conservation" to "authenticated";

grant update on table "public"."aides_etats_conservation" to "authenticated";

grant delete on table "public"."aides_etats_conservation" to "service_role";

grant insert on table "public"."aides_etats_conservation" to "service_role";

grant references on table "public"."aides_etats_conservation" to "service_role";

grant select on table "public"."aides_etats_conservation" to "service_role";

grant trigger on table "public"."aides_etats_conservation" to "service_role";

grant truncate on table "public"."aides_etats_conservation" to "service_role";

grant update on table "public"."aides_etats_conservation" to "service_role";

grant delete on table "public"."aides_proprietaires" to "anon";

grant insert on table "public"."aides_proprietaires" to "anon";

grant references on table "public"."aides_proprietaires" to "anon";

grant select on table "public"."aides_proprietaires" to "anon";

grant trigger on table "public"."aides_proprietaires" to "anon";

grant truncate on table "public"."aides_proprietaires" to "anon";

grant update on table "public"."aides_proprietaires" to "anon";

grant delete on table "public"."aides_proprietaires" to "authenticated";

grant insert on table "public"."aides_proprietaires" to "authenticated";

grant references on table "public"."aides_proprietaires" to "authenticated";

grant select on table "public"."aides_proprietaires" to "authenticated";

grant trigger on table "public"."aides_proprietaires" to "authenticated";

grant truncate on table "public"."aides_proprietaires" to "authenticated";

grant update on table "public"."aides_proprietaires" to "authenticated";

grant delete on table "public"."aides_proprietaires" to "service_role";

grant insert on table "public"."aides_proprietaires" to "service_role";

grant references on table "public"."aides_proprietaires" to "service_role";

grant select on table "public"."aides_proprietaires" to "service_role";

grant trigger on table "public"."aides_proprietaires" to "service_role";

grant truncate on table "public"."aides_proprietaires" to "service_role";

grant update on table "public"."aides_proprietaires" to "service_role";

grant delete on table "public"."aides_protections" to "anon";

grant insert on table "public"."aides_protections" to "anon";

grant references on table "public"."aides_protections" to "anon";

grant select on table "public"."aides_protections" to "anon";

grant trigger on table "public"."aides_protections" to "anon";

grant truncate on table "public"."aides_protections" to "anon";

grant update on table "public"."aides_protections" to "anon";

grant delete on table "public"."aides_protections" to "authenticated";

grant insert on table "public"."aides_protections" to "authenticated";

grant references on table "public"."aides_protections" to "authenticated";

grant select on table "public"."aides_protections" to "authenticated";

grant trigger on table "public"."aides_protections" to "authenticated";

grant truncate on table "public"."aides_protections" to "authenticated";

grant update on table "public"."aides_protections" to "authenticated";

grant delete on table "public"."aides_protections" to "service_role";

grant insert on table "public"."aides_protections" to "service_role";

grant references on table "public"."aides_protections" to "service_role";

grant select on table "public"."aides_protections" to "service_role";

grant trigger on table "public"."aides_protections" to "service_role";

grant truncate on table "public"."aides_protections" to "service_role";

grant update on table "public"."aides_protections" to "service_role";

grant delete on table "public"."aides_regions" to "anon";

grant insert on table "public"."aides_regions" to "anon";

grant references on table "public"."aides_regions" to "anon";

grant select on table "public"."aides_regions" to "anon";

grant trigger on table "public"."aides_regions" to "anon";

grant truncate on table "public"."aides_regions" to "anon";

grant update on table "public"."aides_regions" to "anon";

grant delete on table "public"."aides_regions" to "authenticated";

grant insert on table "public"."aides_regions" to "authenticated";

grant references on table "public"."aides_regions" to "authenticated";

grant select on table "public"."aides_regions" to "authenticated";

grant trigger on table "public"."aides_regions" to "authenticated";

grant truncate on table "public"."aides_regions" to "authenticated";

grant update on table "public"."aides_regions" to "authenticated";

grant delete on table "public"."aides_regions" to "service_role";

grant insert on table "public"."aides_regions" to "service_role";

grant references on table "public"."aides_regions" to "service_role";

grant select on table "public"."aides_regions" to "service_role";

grant trigger on table "public"."aides_regions" to "service_role";

grant truncate on table "public"."aides_regions" to "service_role";

grant update on table "public"."aides_regions" to "service_role";

grant delete on table "public"."aides_segments" to "anon";

grant insert on table "public"."aides_segments" to "anon";

grant references on table "public"."aides_segments" to "anon";

grant select on table "public"."aides_segments" to "anon";

grant trigger on table "public"."aides_segments" to "anon";

grant truncate on table "public"."aides_segments" to "anon";

grant update on table "public"."aides_segments" to "anon";

grant delete on table "public"."aides_segments" to "authenticated";

grant insert on table "public"."aides_segments" to "authenticated";

grant references on table "public"."aides_segments" to "authenticated";

grant select on table "public"."aides_segments" to "authenticated";

grant trigger on table "public"."aides_segments" to "authenticated";

grant truncate on table "public"."aides_segments" to "authenticated";

grant update on table "public"."aides_segments" to "authenticated";

grant delete on table "public"."aides_segments" to "service_role";

grant insert on table "public"."aides_segments" to "service_role";

grant references on table "public"."aides_segments" to "service_role";

grant select on table "public"."aides_segments" to "service_role";

grant trigger on table "public"."aides_segments" to "service_role";

grant truncate on table "public"."aides_segments" to "service_role";

grant update on table "public"."aides_segments" to "service_role";

grant delete on table "public"."aides_travaux" to "anon";

grant insert on table "public"."aides_travaux" to "anon";

grant references on table "public"."aides_travaux" to "anon";

grant select on table "public"."aides_travaux" to "anon";

grant trigger on table "public"."aides_travaux" to "anon";

grant truncate on table "public"."aides_travaux" to "anon";

grant update on table "public"."aides_travaux" to "anon";

grant delete on table "public"."aides_travaux" to "authenticated";

grant insert on table "public"."aides_travaux" to "authenticated";

grant references on table "public"."aides_travaux" to "authenticated";

grant select on table "public"."aides_travaux" to "authenticated";

grant trigger on table "public"."aides_travaux" to "authenticated";

grant truncate on table "public"."aides_travaux" to "authenticated";

grant update on table "public"."aides_travaux" to "authenticated";

grant delete on table "public"."aides_travaux" to "service_role";

grant insert on table "public"."aides_travaux" to "service_role";

grant references on table "public"."aides_travaux" to "service_role";

grant select on table "public"."aides_travaux" to "service_role";

grant trigger on table "public"."aides_travaux" to "service_role";

grant truncate on table "public"."aides_travaux" to "service_role";

grant update on table "public"."aides_travaux" to "service_role";

grant delete on table "public"."aides_v2" to "anon";

grant insert on table "public"."aides_v2" to "anon";

grant references on table "public"."aides_v2" to "anon";

grant select on table "public"."aides_v2" to "anon";

grant trigger on table "public"."aides_v2" to "anon";

grant truncate on table "public"."aides_v2" to "anon";

grant update on table "public"."aides_v2" to "anon";

grant delete on table "public"."aides_v2" to "authenticated";

grant insert on table "public"."aides_v2" to "authenticated";

grant references on table "public"."aides_v2" to "authenticated";

grant select on table "public"."aides_v2" to "authenticated";

grant trigger on table "public"."aides_v2" to "authenticated";

grant truncate on table "public"."aides_v2" to "authenticated";

grant update on table "public"."aides_v2" to "authenticated";

grant delete on table "public"."aides_v2" to "service_role";

grant insert on table "public"."aides_v2" to "service_role";

grant references on table "public"."aides_v2" to "service_role";

grant select on table "public"."aides_v2" to "service_role";

grant trigger on table "public"."aides_v2" to "service_role";

grant truncate on table "public"."aides_v2" to "service_role";

grant update on table "public"."aides_v2" to "service_role";

grant delete on table "public"."communes" to "anon";

grant insert on table "public"."communes" to "anon";

grant references on table "public"."communes" to "anon";

grant select on table "public"."communes" to "anon";

grant trigger on table "public"."communes" to "anon";

grant truncate on table "public"."communes" to "anon";

grant update on table "public"."communes" to "anon";

grant delete on table "public"."communes" to "authenticated";

grant insert on table "public"."communes" to "authenticated";

grant references on table "public"."communes" to "authenticated";

grant select on table "public"."communes" to "authenticated";

grant trigger on table "public"."communes" to "authenticated";

grant truncate on table "public"."communes" to "authenticated";

grant update on table "public"."communes" to "authenticated";

grant delete on table "public"."communes" to "service_role";

grant insert on table "public"."communes" to "service_role";

grant references on table "public"."communes" to "service_role";

grant select on table "public"."communes" to "service_role";

grant trigger on table "public"."communes" to "service_role";

grant truncate on table "public"."communes" to "service_role";

grant update on table "public"."communes" to "service_role";

grant delete on table "public"."diagnostics" to "anon";

grant insert on table "public"."diagnostics" to "anon";

grant references on table "public"."diagnostics" to "anon";

grant select on table "public"."diagnostics" to "anon";

grant trigger on table "public"."diagnostics" to "anon";

grant truncate on table "public"."diagnostics" to "anon";

grant update on table "public"."diagnostics" to "anon";

grant delete on table "public"."diagnostics" to "authenticated";

grant insert on table "public"."diagnostics" to "authenticated";

grant references on table "public"."diagnostics" to "authenticated";

grant select on table "public"."diagnostics" to "authenticated";

grant trigger on table "public"."diagnostics" to "authenticated";

grant truncate on table "public"."diagnostics" to "authenticated";

grant update on table "public"."diagnostics" to "authenticated";

grant delete on table "public"."diagnostics" to "service_role";

grant insert on table "public"."diagnostics" to "service_role";

grant references on table "public"."diagnostics" to "service_role";

grant select on table "public"."diagnostics" to "service_role";

grant trigger on table "public"."diagnostics" to "service_role";

grant truncate on table "public"."diagnostics" to "service_role";

grant update on table "public"."diagnostics" to "service_role";

grant delete on table "public"."documents" to "anon";

grant insert on table "public"."documents" to "anon";

grant references on table "public"."documents" to "anon";

grant select on table "public"."documents" to "anon";

grant trigger on table "public"."documents" to "anon";

grant truncate on table "public"."documents" to "anon";

grant update on table "public"."documents" to "anon";

grant delete on table "public"."documents" to "authenticated";

grant insert on table "public"."documents" to "authenticated";

grant references on table "public"."documents" to "authenticated";

grant select on table "public"."documents" to "authenticated";

grant trigger on table "public"."documents" to "authenticated";

grant truncate on table "public"."documents" to "authenticated";

grant update on table "public"."documents" to "authenticated";

grant delete on table "public"."documents" to "service_role";

grant insert on table "public"."documents" to "service_role";

grant references on table "public"."documents" to "service_role";

grant select on table "public"."documents" to "service_role";

grant trigger on table "public"."documents" to "service_role";

grant truncate on table "public"."documents" to "service_role";

grant update on table "public"."documents" to "service_role";

grant delete on table "public"."dossiers" to "anon";

grant insert on table "public"."dossiers" to "anon";

grant references on table "public"."dossiers" to "anon";

grant select on table "public"."dossiers" to "anon";

grant trigger on table "public"."dossiers" to "anon";

grant truncate on table "public"."dossiers" to "anon";

grant update on table "public"."dossiers" to "anon";

grant delete on table "public"."dossiers" to "authenticated";

grant insert on table "public"."dossiers" to "authenticated";

grant references on table "public"."dossiers" to "authenticated";

grant select on table "public"."dossiers" to "authenticated";

grant trigger on table "public"."dossiers" to "authenticated";

grant truncate on table "public"."dossiers" to "authenticated";

grant update on table "public"."dossiers" to "authenticated";

grant delete on table "public"."dossiers" to "service_role";

grant insert on table "public"."dossiers" to "service_role";

grant references on table "public"."dossiers" to "service_role";

grant select on table "public"."dossiers" to "service_role";

grant trigger on table "public"."dossiers" to "service_role";

grant truncate on table "public"."dossiers" to "service_role";

grant update on table "public"."dossiers" to "service_role";

grant delete on table "public"."merimee_buildings" to "anon";

grant insert on table "public"."merimee_buildings" to "anon";

grant references on table "public"."merimee_buildings" to "anon";

grant select on table "public"."merimee_buildings" to "anon";

grant trigger on table "public"."merimee_buildings" to "anon";

grant truncate on table "public"."merimee_buildings" to "anon";

grant update on table "public"."merimee_buildings" to "anon";

grant delete on table "public"."merimee_buildings" to "authenticated";

grant insert on table "public"."merimee_buildings" to "authenticated";

grant references on table "public"."merimee_buildings" to "authenticated";

grant select on table "public"."merimee_buildings" to "authenticated";

grant trigger on table "public"."merimee_buildings" to "authenticated";

grant truncate on table "public"."merimee_buildings" to "authenticated";

grant update on table "public"."merimee_buildings" to "authenticated";

grant delete on table "public"."merimee_buildings" to "service_role";

grant insert on table "public"."merimee_buildings" to "service_role";

grant references on table "public"."merimee_buildings" to "service_role";

grant select on table "public"."merimee_buildings" to "service_role";

grant trigger on table "public"."merimee_buildings" to "service_role";

grant truncate on table "public"."merimee_buildings" to "service_role";

grant update on table "public"."merimee_buildings" to "service_role";

grant delete on table "public"."monuments" to "anon";

grant insert on table "public"."monuments" to "anon";

grant references on table "public"."monuments" to "anon";

grant select on table "public"."monuments" to "anon";

grant trigger on table "public"."monuments" to "anon";

grant truncate on table "public"."monuments" to "anon";

grant update on table "public"."monuments" to "anon";

grant delete on table "public"."monuments" to "authenticated";

grant insert on table "public"."monuments" to "authenticated";

grant references on table "public"."monuments" to "authenticated";

grant select on table "public"."monuments" to "authenticated";

grant trigger on table "public"."monuments" to "authenticated";

grant truncate on table "public"."monuments" to "authenticated";

grant update on table "public"."monuments" to "authenticated";

grant delete on table "public"."monuments" to "service_role";

grant insert on table "public"."monuments" to "service_role";

grant references on table "public"."monuments" to "service_role";

grant select on table "public"."monuments" to "service_role";

grant trigger on table "public"."monuments" to "service_role";

grant truncate on table "public"."monuments" to "service_role";

grant update on table "public"."monuments" to "service_role";

grant delete on table "public"."notifications" to "anon";

grant insert on table "public"."notifications" to "anon";

grant references on table "public"."notifications" to "anon";

grant select on table "public"."notifications" to "anon";

grant trigger on table "public"."notifications" to "anon";

grant truncate on table "public"."notifications" to "anon";

grant update on table "public"."notifications" to "anon";

grant delete on table "public"."notifications" to "authenticated";

grant insert on table "public"."notifications" to "authenticated";

grant references on table "public"."notifications" to "authenticated";

grant select on table "public"."notifications" to "authenticated";

grant trigger on table "public"."notifications" to "authenticated";

grant truncate on table "public"."notifications" to "authenticated";

grant update on table "public"."notifications" to "authenticated";

grant delete on table "public"."notifications" to "service_role";

grant insert on table "public"."notifications" to "service_role";

grant references on table "public"."notifications" to "service_role";

grant select on table "public"."notifications" to "service_role";

grant trigger on table "public"."notifications" to "service_role";

grant truncate on table "public"."notifications" to "service_role";

grant update on table "public"."notifications" to "service_role";

grant delete on table "public"."prospects" to "anon";

grant insert on table "public"."prospects" to "anon";

grant references on table "public"."prospects" to "anon";

grant select on table "public"."prospects" to "anon";

grant trigger on table "public"."prospects" to "anon";

grant truncate on table "public"."prospects" to "anon";

grant update on table "public"."prospects" to "anon";

grant delete on table "public"."prospects" to "authenticated";

grant insert on table "public"."prospects" to "authenticated";

grant references on table "public"."prospects" to "authenticated";

grant select on table "public"."prospects" to "authenticated";

grant trigger on table "public"."prospects" to "authenticated";

grant truncate on table "public"."prospects" to "authenticated";

grant update on table "public"."prospects" to "authenticated";

grant delete on table "public"."prospects" to "service_role";

grant insert on table "public"."prospects" to "service_role";

grant references on table "public"."prospects" to "service_role";

grant select on table "public"."prospects" to "service_role";

grant trigger on table "public"."prospects" to "service_role";

grant truncate on table "public"."prospects" to "service_role";

grant update on table "public"."prospects" to "service_role";

grant delete on table "public"."ref_etats_conservation" to "anon";

grant insert on table "public"."ref_etats_conservation" to "anon";

grant references on table "public"."ref_etats_conservation" to "anon";

grant select on table "public"."ref_etats_conservation" to "anon";

grant trigger on table "public"."ref_etats_conservation" to "anon";

grant truncate on table "public"."ref_etats_conservation" to "anon";

grant update on table "public"."ref_etats_conservation" to "anon";

grant delete on table "public"."ref_etats_conservation" to "authenticated";

grant insert on table "public"."ref_etats_conservation" to "authenticated";

grant references on table "public"."ref_etats_conservation" to "authenticated";

grant select on table "public"."ref_etats_conservation" to "authenticated";

grant trigger on table "public"."ref_etats_conservation" to "authenticated";

grant truncate on table "public"."ref_etats_conservation" to "authenticated";

grant update on table "public"."ref_etats_conservation" to "authenticated";

grant delete on table "public"."ref_etats_conservation" to "service_role";

grant insert on table "public"."ref_etats_conservation" to "service_role";

grant references on table "public"."ref_etats_conservation" to "service_role";

grant select on table "public"."ref_etats_conservation" to "service_role";

grant trigger on table "public"."ref_etats_conservation" to "service_role";

grant truncate on table "public"."ref_etats_conservation" to "service_role";

grant update on table "public"."ref_etats_conservation" to "service_role";

grant delete on table "public"."ref_proprietaires" to "anon";

grant insert on table "public"."ref_proprietaires" to "anon";

grant references on table "public"."ref_proprietaires" to "anon";

grant select on table "public"."ref_proprietaires" to "anon";

grant trigger on table "public"."ref_proprietaires" to "anon";

grant truncate on table "public"."ref_proprietaires" to "anon";

grant update on table "public"."ref_proprietaires" to "anon";

grant delete on table "public"."ref_proprietaires" to "authenticated";

grant insert on table "public"."ref_proprietaires" to "authenticated";

grant references on table "public"."ref_proprietaires" to "authenticated";

grant select on table "public"."ref_proprietaires" to "authenticated";

grant trigger on table "public"."ref_proprietaires" to "authenticated";

grant truncate on table "public"."ref_proprietaires" to "authenticated";

grant update on table "public"."ref_proprietaires" to "authenticated";

grant delete on table "public"."ref_proprietaires" to "service_role";

grant insert on table "public"."ref_proprietaires" to "service_role";

grant references on table "public"."ref_proprietaires" to "service_role";

grant select on table "public"."ref_proprietaires" to "service_role";

grant trigger on table "public"."ref_proprietaires" to "service_role";

grant truncate on table "public"."ref_proprietaires" to "service_role";

grant update on table "public"."ref_proprietaires" to "service_role";

grant delete on table "public"."ref_protections" to "anon";

grant insert on table "public"."ref_protections" to "anon";

grant references on table "public"."ref_protections" to "anon";

grant select on table "public"."ref_protections" to "anon";

grant trigger on table "public"."ref_protections" to "anon";

grant truncate on table "public"."ref_protections" to "anon";

grant update on table "public"."ref_protections" to "anon";

grant delete on table "public"."ref_protections" to "authenticated";

grant insert on table "public"."ref_protections" to "authenticated";

grant references on table "public"."ref_protections" to "authenticated";

grant select on table "public"."ref_protections" to "authenticated";

grant trigger on table "public"."ref_protections" to "authenticated";

grant truncate on table "public"."ref_protections" to "authenticated";

grant update on table "public"."ref_protections" to "authenticated";

grant delete on table "public"."ref_protections" to "service_role";

grant insert on table "public"."ref_protections" to "service_role";

grant references on table "public"."ref_protections" to "service_role";

grant select on table "public"."ref_protections" to "service_role";

grant trigger on table "public"."ref_protections" to "service_role";

grant truncate on table "public"."ref_protections" to "service_role";

grant update on table "public"."ref_protections" to "service_role";

grant delete on table "public"."ref_segments" to "anon";

grant insert on table "public"."ref_segments" to "anon";

grant references on table "public"."ref_segments" to "anon";

grant select on table "public"."ref_segments" to "anon";

grant trigger on table "public"."ref_segments" to "anon";

grant truncate on table "public"."ref_segments" to "anon";

grant update on table "public"."ref_segments" to "anon";

grant delete on table "public"."ref_segments" to "authenticated";

grant insert on table "public"."ref_segments" to "authenticated";

grant references on table "public"."ref_segments" to "authenticated";

grant select on table "public"."ref_segments" to "authenticated";

grant trigger on table "public"."ref_segments" to "authenticated";

grant truncate on table "public"."ref_segments" to "authenticated";

grant update on table "public"."ref_segments" to "authenticated";

grant delete on table "public"."ref_segments" to "service_role";

grant insert on table "public"."ref_segments" to "service_role";

grant references on table "public"."ref_segments" to "service_role";

grant select on table "public"."ref_segments" to "service_role";

grant trigger on table "public"."ref_segments" to "service_role";

grant truncate on table "public"."ref_segments" to "service_role";

grant update on table "public"."ref_segments" to "service_role";

grant delete on table "public"."ref_travaux" to "anon";

grant insert on table "public"."ref_travaux" to "anon";

grant references on table "public"."ref_travaux" to "anon";

grant select on table "public"."ref_travaux" to "anon";

grant trigger on table "public"."ref_travaux" to "anon";

grant truncate on table "public"."ref_travaux" to "anon";

grant update on table "public"."ref_travaux" to "anon";

grant delete on table "public"."ref_travaux" to "authenticated";

grant insert on table "public"."ref_travaux" to "authenticated";

grant references on table "public"."ref_travaux" to "authenticated";

grant select on table "public"."ref_travaux" to "authenticated";

grant trigger on table "public"."ref_travaux" to "authenticated";

grant truncate on table "public"."ref_travaux" to "authenticated";

grant update on table "public"."ref_travaux" to "authenticated";

grant delete on table "public"."ref_travaux" to "service_role";

grant insert on table "public"."ref_travaux" to "service_role";

grant references on table "public"."ref_travaux" to "service_role";

grant select on table "public"."ref_travaux" to "service_role";

grant trigger on table "public"."ref_travaux" to "service_role";

grant truncate on table "public"."ref_travaux" to "service_role";

grant update on table "public"."ref_travaux" to "service_role";

grant delete on table "public"."users" to "anon";

grant insert on table "public"."users" to "anon";

grant references on table "public"."users" to "anon";

grant select on table "public"."users" to "anon";

grant trigger on table "public"."users" to "anon";

grant truncate on table "public"."users" to "anon";

grant update on table "public"."users" to "anon";

grant delete on table "public"."users" to "authenticated";

grant insert on table "public"."users" to "authenticated";

grant references on table "public"."users" to "authenticated";

grant select on table "public"."users" to "authenticated";

grant trigger on table "public"."users" to "authenticated";

grant truncate on table "public"."users" to "authenticated";

grant update on table "public"."users" to "authenticated";

grant delete on table "public"."users" to "service_role";

grant insert on table "public"."users" to "service_role";

grant references on table "public"."users" to "service_role";

grant select on table "public"."users" to "service_role";

grant trigger on table "public"."users" to "service_role";

grant truncate on table "public"."users" to "service_role";

grant update on table "public"."users" to "service_role";


  create policy "aides_departements_read"
  on "public"."aides_departements"
  as permissive
  for select
  to authenticated
using (true);



  create policy "aides_etats_conservation_read"
  on "public"."aides_etats_conservation"
  as permissive
  for select
  to authenticated
using (true);



  create policy "aides_proprietaires_read"
  on "public"."aides_proprietaires"
  as permissive
  for select
  to authenticated
using (true);



  create policy "aides_protections_read"
  on "public"."aides_protections"
  as permissive
  for select
  to authenticated
using (true);



  create policy "aides_regions_read"
  on "public"."aides_regions"
  as permissive
  for select
  to authenticated
using (true);



  create policy "aides_segments_read"
  on "public"."aides_segments"
  as permissive
  for select
  to authenticated
using (true);



  create policy "aides_travaux_read"
  on "public"."aides_travaux"
  as permissive
  for select
  to authenticated
using (true);



  create policy "aides_v2_read"
  on "public"."aides_v2"
  as permissive
  for select
  to authenticated
using (true);



  create policy "Users can delete their own diagnostics"
  on "public"."diagnostics"
  as permissive
  for delete
  to public
using ((auth.uid() = user_id));



  create policy "Users can insert their own diagnostics"
  on "public"."diagnostics"
  as permissive
  for insert
  to public
with check ((auth.uid() = user_id));



  create policy "Users can read their own diagnostics"
  on "public"."diagnostics"
  as permissive
  for select
  to public
using ((auth.uid() = user_id));



  create policy "documents: delete own"
  on "public"."documents"
  as permissive
  for delete
  to public
using ((auth.uid() = user_id));



  create policy "documents: insert own"
  on "public"."documents"
  as permissive
  for insert
  to public
with check ((auth.uid() = user_id));



  create policy "documents: select own"
  on "public"."documents"
  as permissive
  for select
  to public
using ((auth.uid() = user_id));



  create policy "documents: update own"
  on "public"."documents"
  as permissive
  for update
  to public
using ((auth.uid() = user_id));



  create policy "dossiers: delete own"
  on "public"."dossiers"
  as permissive
  for delete
  to public
using ((auth.uid() = user_id));



  create policy "dossiers: insert own"
  on "public"."dossiers"
  as permissive
  for insert
  to public
with check ((auth.uid() = user_id));



  create policy "dossiers: select own"
  on "public"."dossiers"
  as permissive
  for select
  to public
using ((auth.uid() = user_id));



  create policy "dossiers: update own"
  on "public"."dossiers"
  as permissive
  for update
  to public
using ((auth.uid() = user_id));



  create policy "Enable insert for authenticated users only"
  on "public"."merimee_buildings"
  as permissive
  for insert
  to authenticated
with check (true);



  create policy "Enable read access for all users"
  on "public"."merimee_buildings"
  as permissive
  for select
  to public
using (true);



  create policy "monuments: delete own"
  on "public"."monuments"
  as permissive
  for delete
  to public
using ((auth.uid() = user_id));



  create policy "monuments: insert own"
  on "public"."monuments"
  as permissive
  for insert
  to public
with check ((auth.uid() = user_id));



  create policy "monuments: select own"
  on "public"."monuments"
  as permissive
  for select
  to public
using ((auth.uid() = user_id));



  create policy "monuments: update own"
  on "public"."monuments"
  as permissive
  for update
  to public
using ((auth.uid() = user_id));



  create policy "notifications: delete own"
  on "public"."notifications"
  as permissive
  for delete
  to public
using ((auth.uid() = user_id));



  create policy "notifications: insert own"
  on "public"."notifications"
  as permissive
  for insert
  to public
with check ((auth.uid() = user_id));



  create policy "notifications: select own"
  on "public"."notifications"
  as permissive
  for select
  to public
using ((auth.uid() = user_id));



  create policy "notifications: update own"
  on "public"."notifications"
  as permissive
  for update
  to public
using ((auth.uid() = user_id));



  create policy "prospects_delete"
  on "public"."prospects"
  as permissive
  for delete
  to public
using ((auth.uid() = btp_user_id));



  create policy "prospects_insert"
  on "public"."prospects"
  as permissive
  for insert
  to public
with check ((auth.uid() = btp_user_id));



  create policy "prospects_select"
  on "public"."prospects"
  as permissive
  for select
  to public
using ((auth.uid() = btp_user_id));



  create policy "prospects_update"
  on "public"."prospects"
  as permissive
  for update
  to public
using ((auth.uid() = btp_user_id));



  create policy "ref_etats_conservation_read"
  on "public"."ref_etats_conservation"
  as permissive
  for select
  to authenticated
using (true);



  create policy "ref_proprietaires_read"
  on "public"."ref_proprietaires"
  as permissive
  for select
  to authenticated
using (true);



  create policy "ref_protections_read"
  on "public"."ref_protections"
  as permissive
  for select
  to authenticated
using (true);



  create policy "ref_segments_read"
  on "public"."ref_segments"
  as permissive
  for select
  to authenticated
using (true);



  create policy "ref_travaux_read"
  on "public"."ref_travaux"
  as permissive
  for select
  to authenticated
using (true);



  create policy "users: select own"
  on "public"."users"
  as permissive
  for select
  to public
using ((auth.uid() = id));



  create policy "users: update own"
  on "public"."users"
  as permissive
  for update
  to public
using ((auth.uid() = id));


CREATE TRIGGER dossiers_modified_at BEFORE UPDATE ON public.dossiers FOR EACH ROW EXECUTE FUNCTION public.update_dossier_modification();

CREATE TRIGGER monuments_updated_at BEFORE UPDATE ON public.monuments FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

CREATE TRIGGER prospects_updated_at BEFORE UPDATE ON public.prospects FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

CREATE TRIGGER users_updated_at BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();


  create policy "Users can delete their own documents"
  on "storage"."objects"
  as permissive
  for delete
  to authenticated
using (((bucket_id = 'documents'::text) AND ((storage.foldername(name))[1] = (auth.uid())::text)));



  create policy "Users can read their own documents flreew_0"
  on "storage"."objects"
  as permissive
  for select
  to authenticated
using (((bucket_id = 'documents'::text) AND ((storage.foldername(name))[1] = (auth.uid())::text)));



  create policy "Users can read their own documents"
  on "storage"."objects"
  as permissive
  for select
  to authenticated
using (((bucket_id = 'documents'::text) AND ((storage.foldername(name))[1] = (auth.uid())::text)));



  create policy "Users can upload their own documents"
  on "storage"."objects"
  as permissive
  for insert
  to authenticated
with check (((bucket_id = 'documents'::text) AND ((storage.foldername(name))[1] = (auth.uid())::text)));



  create policy "documents_public_read"
  on "storage"."objects"
  as permissive
  for select
  to public
using ((bucket_id = 'documents'::text));



  create policy "documents_user_delete"
  on "storage"."objects"
  as permissive
  for delete
  to public
using (((bucket_id = 'documents'::text) AND ((auth.uid())::text = (storage.foldername(name))[1])));



  create policy "documents_user_insert"
  on "storage"."objects"
  as permissive
  for insert
  to public
with check (((bucket_id = 'documents'::text) AND ((auth.uid())::text = (storage.foldername(name))[1])));



