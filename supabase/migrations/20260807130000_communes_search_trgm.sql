-- Recherche de communes « contient », frappe par frappe.
--
-- L'autocomplétion de la commune (création de projet, onboarding) interroge
-- `communes.nom_commune_matching` en ILIKE '%saisie%' : un index B-tree ne sert
-- à rien sur un motif non ancré, d'où le trigramme GIN. Même dispositif que
-- l'index de recherche Mérimée (20260629120000).

create extension if not exists pg_trgm with schema extensions;
set search_path = public, extensions;

create index if not exists communes_nom_matching_trgm
  on public.communes using gin (nom_commune_matching gin_trgm_ops);
