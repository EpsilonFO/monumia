-- Remove the user-segment filter from aide matching.
--
-- The `segment` attribute on users (commune / prive / btp) is now used only
-- to drive UX routing and to fetch commune population at runtime — it is no
-- longer a criterion for aide eligibility. Aide-level eligibility is fully
-- captured by `proprietaire` (a monument attribute) and the other join
-- tables (protections, travaux, régions, départements, etc.).

DROP FUNCTION IF EXISTS public.prefiltrer_aides(text, text, text[], text, text, text, integer, text);

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
  SELECT DISTINCT a.id
  FROM aides_v2 a
  WHERE
    (p_protection IS NULL
     OR NOT EXISTS (SELECT 1 FROM aides_protections ap WHERE ap.aide_id = a.id)
     OR EXISTS (SELECT 1 FROM aides_protections ap WHERE ap.aide_id = a.id AND ap.protection_code = p_protection))

    AND (p_proprietaire IS NULL
     OR NOT EXISTS (SELECT 1 FROM aides_proprietaires ap WHERE ap.aide_id = a.id)
     OR EXISTS (SELECT 1 FROM aides_proprietaires ap WHERE ap.aide_id = a.id AND ap.proprietaire_code = p_proprietaire))

    AND (p_travaux IS NULL
     OR NOT EXISTS (SELECT 1 FROM aides_travaux at2 WHERE at2.aide_id = a.id)
     OR EXISTS (SELECT 1 FROM aides_travaux at2 WHERE at2.aide_id = a.id AND at2.travaux_code = ANY(p_travaux)))

    AND (p_region IS NULL
     OR NOT EXISTS (SELECT 1 FROM aides_regions ar WHERE ar.aide_id = a.id)
     OR EXISTS (SELECT 1 FROM aides_regions ar WHERE ar.aide_id = a.id AND ar.region_code = p_region))

    AND (p_departement IS NULL
     OR NOT EXISTS (SELECT 1 FROM aides_departements ad WHERE ad.aide_id = a.id)
     OR EXISTS (SELECT 1 FROM aides_departements ad WHERE ad.aide_id = a.id AND ad.departement_code = p_departement))

    AND (a.commune_max_population IS NULL OR p_population IS NULL OR p_population <= a.commune_max_population)

    AND (p_etat_conservation IS NULL
     OR NOT EXISTS (SELECT 1 FROM aides_etats_conservation ae WHERE ae.aide_id = a.id)
     OR EXISTS (SELECT 1 FROM aides_etats_conservation ae WHERE ae.aide_id = a.id AND ae.etat_conservation_code = p_etat_conservation))

    AND (a.permanent = true OR a.date_limite IS NULL OR a.date_limite >= CURRENT_DATE)
  ;
$function$;

DROP TABLE IF EXISTS public.aides_segments CASCADE;
DROP TABLE IF EXISTS public.ref_segments CASCADE;
