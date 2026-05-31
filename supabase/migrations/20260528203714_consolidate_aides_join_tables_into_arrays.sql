-- Consolidate the six aides_* join tables (departements, regions, protections,
-- proprietaires, travaux, etats_conservation) into array columns on aides_v2.
--
-- Each aide previously had one row per (aide_id, code) across six tables; the
-- pre-filter RPC fanned out with as many EXISTS subqueries. We now store the
-- codes as `text[]` columns on aides_v2 itself, which collapses each aide to a
-- single row and replaces the EXISTS subqueries with `&&` (array overlap) /
-- `= ANY()` checks.

-- ── 1. Add the array columns ────────────────────────────────────────────────

ALTER TABLE public.aides_v2
    ADD COLUMN IF NOT EXISTS protections        text[] NOT NULL DEFAULT '{}'::text[],
    ADD COLUMN IF NOT EXISTS proprietaires      text[] NOT NULL DEFAULT '{}'::text[],
    ADD COLUMN IF NOT EXISTS travaux            text[] NOT NULL DEFAULT '{}'::text[],
    ADD COLUMN IF NOT EXISTS regions            text[] NOT NULL DEFAULT '{}'::text[],
    ADD COLUMN IF NOT EXISTS departements       text[] NOT NULL DEFAULT '{}'::text[],
    ADD COLUMN IF NOT EXISTS etats_conservation text[] NOT NULL DEFAULT '{}'::text[];

-- ── 2. Backfill from the join tables ───────────────────────────────────────
-- One UPDATE per join table; each aggregates the join's codes into a sorted,
-- deduplicated array. We deliberately leave aides absent from a join with the
-- default '{}' — "no row in the join" historically meant "no restriction",
-- and the new RPC keeps that semantics (empty array → no filter).

UPDATE public.aides_v2 a
SET protections = sub.codes
FROM (
    SELECT aide_id, array_agg(DISTINCT protection_code ORDER BY protection_code) AS codes
    FROM public.aides_protections
    GROUP BY aide_id
) sub
WHERE a.id = sub.aide_id;

UPDATE public.aides_v2 a
SET proprietaires = sub.codes
FROM (
    SELECT aide_id, array_agg(DISTINCT proprietaire_code ORDER BY proprietaire_code) AS codes
    FROM public.aides_proprietaires
    GROUP BY aide_id
) sub
WHERE a.id = sub.aide_id;

UPDATE public.aides_v2 a
SET travaux = sub.codes
FROM (
    SELECT aide_id, array_agg(DISTINCT travaux_code ORDER BY travaux_code) AS codes
    FROM public.aides_travaux
    GROUP BY aide_id
) sub
WHERE a.id = sub.aide_id;

UPDATE public.aides_v2 a
SET regions = sub.codes
FROM (
    SELECT aide_id, array_agg(DISTINCT region_code ORDER BY region_code) AS codes
    FROM public.aides_regions
    GROUP BY aide_id
) sub
WHERE a.id = sub.aide_id;

UPDATE public.aides_v2 a
SET departements = sub.codes
FROM (
    SELECT aide_id, array_agg(DISTINCT departement_code ORDER BY departement_code) AS codes
    FROM public.aides_departements
    GROUP BY aide_id
) sub
WHERE a.id = sub.aide_id;

UPDATE public.aides_v2 a
SET etats_conservation = sub.codes
FROM (
    SELECT aide_id, array_agg(DISTINCT etat_conservation_code ORDER BY etat_conservation_code) AS codes
    FROM public.aides_etats_conservation
    GROUP BY aide_id
) sub
WHERE a.id = sub.aide_id;

-- ── 3. GIN indexes for the array-contained / overlap predicates ────────────
-- The new prefiltrer_aides function uses `code = ANY(column)` and `column && array[...]`
-- which both benefit from a GIN index on the array column.

CREATE INDEX IF NOT EXISTS idx_aides_v2_protections        ON public.aides_v2 USING gin (protections);
CREATE INDEX IF NOT EXISTS idx_aides_v2_proprietaires      ON public.aides_v2 USING gin (proprietaires);
CREATE INDEX IF NOT EXISTS idx_aides_v2_travaux            ON public.aides_v2 USING gin (travaux);
CREATE INDEX IF NOT EXISTS idx_aides_v2_regions            ON public.aides_v2 USING gin (regions);
CREATE INDEX IF NOT EXISTS idx_aides_v2_departements       ON public.aides_v2 USING gin (departements);
CREATE INDEX IF NOT EXISTS idx_aides_v2_etats_conservation ON public.aides_v2 USING gin (etats_conservation);

-- ── 4. Rewrite prefiltrer_aides to read from the arrays ───────────────────
-- Same signature, same semantics: an empty array column means "no restriction
-- on this dimension", a non-empty array means "the monument's value (or one of
-- the requested travaux) must appear in the array".

DROP FUNCTION IF EXISTS public.prefiltrer_aides(text, text, text[], text, text, integer, text);

CREATE OR REPLACE FUNCTION public.prefiltrer_aides(
    p_protection text DEFAULT NULL::text,
    p_proprietaire text DEFAULT NULL::text,
    p_travaux text[] DEFAULT NULL::text[],
    p_region text DEFAULT NULL::text,
    p_departement text DEFAULT NULL::text,
    p_population integer DEFAULT NULL::integer,
    p_etat_conservation text DEFAULT NULL::text
)
 RETURNS TABLE(aide_id uuid)
 LANGUAGE sql
 STABLE
AS $function$
  SELECT a.id
  FROM public.aides_v2 a
  WHERE
    (p_protection IS NULL
     OR cardinality(a.protections) = 0
     OR p_protection = ANY(a.protections))

    AND (p_proprietaire IS NULL
     OR cardinality(a.proprietaires) = 0
     OR p_proprietaire = ANY(a.proprietaires))

    AND (p_travaux IS NULL
     OR cardinality(a.travaux) = 0
     OR a.travaux && p_travaux)

    AND (p_region IS NULL
     OR cardinality(a.regions) = 0
     OR p_region = ANY(a.regions))

    AND (p_departement IS NULL
     OR cardinality(a.departements) = 0
     OR p_departement = ANY(a.departements))

    AND (a.commune_max_population IS NULL OR p_population IS NULL OR p_population <= a.commune_max_population)

    AND (p_etat_conservation IS NULL
     OR cardinality(a.etats_conservation) = 0
     OR p_etat_conservation = ANY(a.etats_conservation))

    AND (a.permanent = true OR a.date_limite IS NULL OR a.date_limite >= CURRENT_DATE)
  ;
$function$;

-- ── 5. Drop the now-obsolete join tables ──────────────────────────────────
-- CASCADE because each table is referenced by its own primary-key index and
-- foreign-key constraints from aides_v2 / ref_* tables.

DROP TABLE IF EXISTS public.aides_protections        CASCADE;
DROP TABLE IF EXISTS public.aides_proprietaires      CASCADE;
DROP TABLE IF EXISTS public.aides_travaux            CASCADE;
DROP TABLE IF EXISTS public.aides_regions            CASCADE;
DROP TABLE IF EXISTS public.aides_departements       CASCADE;
DROP TABLE IF EXISTS public.aides_etats_conservation CASCADE;
