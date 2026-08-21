-- Réaligne aides_v3 sur le schéma attendu par le loader — suite de
-- 20260613120000_aides_v3_complete_loader_columns, qui avait oublié deux
-- colonnes.
--
-- Contexte : la table est créée par le dump de référence
-- 20260405170500_remote_schema, qui ne porte ni `raison` ni `taux_min`. La
-- migration 20260515125542_aides_v3, elle, les déclare — mais son
-- `create table if not exists` est un no-op puisque la table existe déjà.
-- Résultat : sur toute base reconstruite depuis les migrations, les deux
-- colonnes manquent, et l'insert du loader échoue en PGRST204
-- « Could not find the 'raison' column of 'aides_v3' in the schema cache ».
--
-- `raison` est NOT NULL côté loader (load_aides_yaml.py fait un
-- `row.setdefault("raison", [])` à l'insert) : le défaut '{}' permet de
-- l'ajouter sur une table déjà peuplée sans réécrire les lignes existantes.
-- Le CHECK reprend à l'identique les quatre finalités de
-- 20260515125542_aides_v3, qui sont aussi les valeurs de RAISONS dans
-- backend/aides_schema.py.
--
-- IF NOT EXISTS partout : no-op sur une base déjà complète (prod, beta, où les
-- colonnes ont été posées hors migration), réparation sur les autres.

alter table public.aides_v3
    add column if not exists raison    text[] not null default '{}'::text[],
    add column if not exists taux_min  numeric;

-- Le CHECK ne peut pas être conditionné par IF NOT EXISTS : on le pose
-- seulement s'il est absent, pour rester rejouable.
do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.aides_v3'::regclass
          and conname = 'aides_v3_raison_check'
    ) then
        alter table public.aides_v3
            add constraint aides_v3_raison_check check (
                raison <@ array[
                    'etude_ingenierie',
                    'restauration_travaux',
                    'valorisation_rayonnement',
                    'fiscalite'
                ]::text[]
            );
    end if;
end
$$;
