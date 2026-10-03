-- Familles thématiques d'une aide — l'axe de cadrage d'un projet « faire vivre
-- le lieu », que `raison` ne sait pas dire : ses quatre valeurs mettent dans le
-- même sac un festival, un gîte et un outil de médiation.
--
-- La colonne est lue par `GET /aides/{id}` quand l'identifiant est un UUID (la
-- fiche vient alors d'`aides_v3` et non du YAML) : sans elle, la même aide
-- exposerait `familles` par son slug et pas par son UUID.
--
-- `familles` est NOT NULL côté loader (`aide_to_row` envoie toujours la liste,
-- vide comprise) : le défaut '{}' permet de l'ajouter sur une table déjà
-- peuplée sans réécrire les lignes existantes. Vide = l'aide concerne tout
-- projet (fail-open), exactement comme une `raison` absente.
--
-- Patron de 20260821013354_reparer_aides_v3_raison_taux_min : `IF NOT EXISTS`
-- partout, CHECK posé seulement s'il est absent, donc rejouable sur une base
-- déjà complète.
--
-- ⚠ À APPLIQUER AVANT tout `load_aides_yaml.py`, y compris en local : sinon
-- l'insert échoue en PGRST204 « Could not find the 'familles' column of
-- 'aides_v3' in the schema cache » (même histoire que `raison`).
--
-- Les 13 valeurs du CHECK sont celles de `labels.FAMILLES_LABELS`, d'où
-- `aides_schema.FAMILLES` dérive et que `frontend/src/constants/familles.ts`
-- reproduit. Trois lieux, trois tests qui les comparent.

alter table public.aides_v3
    add column if not exists familles text[] not null default '{}'::text[];

-- Le CHECK ne peut pas être conditionné par IF NOT EXISTS : on le pose
-- seulement s'il est absent, pour rester rejouable.
do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.aides_v3'::regclass
          and conname = 'aides_v3_familles_check'
    ) then
        alter table public.aides_v3
            add constraint aides_v3_familles_check check (
                familles <@ array[
                    'restauration_bati',
                    'energie_climat',
                    'eau_nature_domaine',
                    'securite_risques',
                    'parcs_jardins_paysages',
                    'tourisme_hebergement',
                    'activite_economique_lieu',
                    'spectacles_manifestations',
                    'vie_locale_associative',
                    'mediation_numerique_expositions',
                    'accessibilite_publics',
                    'etudes_ingenierie',
                    'labels_passerelles'
                ]::text[]
            );
    end if;
end
$$;
