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
  language sql
  stable
as $function$
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
        and public.unaccent(lower(c_direct.nom_commune))
            <> public.unaccent(lower(coalesce(mb.commune_forme_index, '')))
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
  where (
    select bool_and(
      public.unaccent(
        coalesce(mb.titre_editorial_de_la_notice, '') || ' ' ||
        coalesce(mb.commune_forme_index, '')           || ' ' ||
        coalesce(mb.departement_en_lettres, '')        || ' ' ||
        coalesce(mb.region, '')                        || ' ' ||
        coalesce(mb.reference, '')                     || ' ' ||
        coalesce(mb.typologie_de_la_protection, '')
      ) ilike '%' || public.unaccent(t) || '%'
    )
    from unnest(tokens) t
  );
$function$;
