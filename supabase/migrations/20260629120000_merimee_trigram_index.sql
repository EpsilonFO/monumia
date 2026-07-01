-- Accélère la recherche Mérimée : remplace le full scan + unaccent/ILIKE par ligne
-- par un index trigramme GIN sur une colonne de recherche pré-calculée.

create extension if not exists pg_trgm with schema extensions;
create extension if not exists unaccent with schema extensions;
set search_path = public, extensions;

-- unaccent() est marquée STABLE (dépend du dictionnaire) et ne peut donc pas
-- servir telle quelle dans une colonne générée ni un index fonctionnel.
-- On l'enveloppe dans une fonction IMMUTABLE, en figeant le dictionnaire.
create or replace function public.immutable_unaccent(text)
  returns text
  language sql
  immutable
  parallel safe
  strict
  set search_path = public, extensions
as $$ select unaccent('unaccent'::regdictionary, $1) $$;

-- Colonne de recherche pré-normalisée (accents retirés), maintenue par Postgres.
alter table public.merimee_buildings
  drop column if exists search_text;

alter table public.merimee_buildings
  add column search_text text
  generated always as (
    public.immutable_unaccent(
      coalesce(titre_editorial_de_la_notice, '') || ' ' ||
      coalesce(commune_forme_index, '')           || ' ' ||
      coalesce(departement_en_lettres, '')        || ' ' ||
      coalesce(region, '')                         || ' ' ||
      coalesce(reference, '')                      || ' ' ||
      coalesce(typologie_de_la_protection, '')
    )
  ) stored;

create index if not exists merimee_buildings_search_trgm
  on public.merimee_buildings using gin (search_text gin_trgm_ops);

-- Recherche : un prédicat ILIKE par token contre la colonne indexée, en SQL
-- dynamique pour que le planificateur exploite l'index trigramme sur chacun.
drop function if exists public.search_merimee(text[]);

create function public.search_merimee(tokens text[])
  returns table(
    reference text,
    region text,
    commune_forme_index text,
    departement_en_lettres text,
    typologie_de_la_protection text,
    titre_editorial_de_la_notice text,
    cog_insee_lors_de_la_protection text,
    commune_actuelle text
  )
  language plpgsql
  stable
  set search_path = public, extensions
as $function$
declare
  predicates text := 'true';
  tok text;
  sql text;
begin
  foreach tok in array tokens loop
    if length(trim(tok)) > 0 then
      predicates := predicates
        || ' and mb.search_text ilike '
        || quote_literal('%' || public.immutable_unaccent(tok) || '%');
    end if;
  end loop;

  sql := format($q$
    select
      mb.reference,
      mb.region,
      mb.commune_forme_index,
      mb.departement_en_lettres,
      mb.typologie_de_la_protection,
      mb.titre_editorial_de_la_notice,
      mb.cog_insee_lors_de_la_protection,
      case
        when c_direct.nom_commune is not null
          and public.immutable_unaccent(lower(c_direct.nom_commune))
              <> public.immutable_unaccent(lower(coalesce(mb.commune_forme_index, '')))
          then c_direct.nom_commune
        when c_mapped.nom_commune is not null
          then c_mapped.nom_commune
        else null
      end as commune_actuelle
    from public.merimee_buildings mb
    left join public.communes c_direct
      on c_direct.code_insee = mb.cog_insee_lors_de_la_protection
    left join public.communes_historique ch
      on ch.ancien_code_insee = mb.cog_insee_lors_de_la_protection
    left join public.communes c_mapped
      on c_mapped.code_insee = ch.nouveau_code_insee
    where %s
    limit 20
  $q$, predicates);

  return query execute sql;
end;
$function$;
