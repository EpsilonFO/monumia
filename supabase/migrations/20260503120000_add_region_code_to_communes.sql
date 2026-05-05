-- Add a normalized kebab-case region_code to communes so the SQL pre-filter
-- in prefiltrer_aides() can match against aides_regions.region_code
-- (which is stored in kebab-case across all seeds and the frontend Region type).
--
-- The existing communes.region column is the INSEE LIBELLE (e.g. "Île-de-France")
-- and is preserved as-is for display / LLM context.

alter table public.communes
  add column if not exists region_code text;

update public.communes
set region_code = case region
    when 'Auvergne-Rhône-Alpes'        then 'auvergne-rhone-alpes'
    when 'Bourgogne-Franche-Comté'     then 'bourgogne-franche-comte'
    when 'Bretagne'                    then 'bretagne'
    when 'Centre-Val de Loire'         then 'centre-val-de-loire'
    when 'Corse'                       then 'corse'
    when 'Grand Est'                   then 'grand-est'
    when 'Hauts-de-France'             then 'hauts-de-france'
    when 'Île-de-France'               then 'ile-de-france'
    when 'Normandie'                   then 'normandie'
    when 'Nouvelle-Aquitaine'          then 'nouvelle-aquitaine'
    when 'Occitanie'                   then 'occitanie'
    when 'Pays de la Loire'            then 'pays-de-la-loire'
    when 'Provence-Alpes-Côte d''Azur' then 'provence-alpes-cote-d-azur'
    -- DOM (kept for completeness even though no aides target them today)
    when 'Guadeloupe'                  then 'guadeloupe'
    when 'Martinique'                  then 'martinique'
    when 'Guyane'                      then 'guyane'
    when 'La Réunion'                  then 'la-reunion'
    when 'Mayotte'                     then 'mayotte'
    else null
end
where region_code is null;

create index if not exists idx_communes_region_code
  on public.communes (region_code);
