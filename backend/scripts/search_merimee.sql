-- Run once in the Supabase SQL editor.
-- Requires the unaccent extension (enabled by default on Supabase).

create extension if not exists unaccent;

drop function if exists search_merimee(text, int);
drop function if exists search_merimee(text);
drop function if exists search_merimee(text[]);

-- Each token must match somewhere in the concatenation of all searchable fields.
create or replace function search_merimee(tokens text[])
returns table (
  reference                     text,
  region                        text,
  commune_forme_index           text,
  departement_en_lettres        text,
  typologie_de_la_protection    text,
  titre_editorial_de_la_notice  text
)
language sql stable
as $$
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
$$;
