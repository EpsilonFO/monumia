-- Retrait de deux codes de travaux du vocabulaire (backend/labels.py,
-- TRAVAUX_RETIRES) :
--   - « toiture » regroupait charpente et couverture : elle devient les deux ;
--   - « equipement_professionnel » n'était cité par aucune aide : il disparaît.
--
-- Réécrit les projets qui les portent, dans l'ordre où ils étaient cochés et
-- sans doublon (« toiture, charpente » → « charpente, couverture »). Un projet
-- qui ne portait qu'« equipement_professionnel » repasse à la liste vide, soit
-- « Pas encore déterminé ».
--
-- Le moteur fait la même traduction à la lecture (normaliser_travaux) : cette
-- migration ne change donc aucun résultat, elle aligne la base sur la grille
-- de l'écran, où ces deux cases n'existent plus.
update public.projets p
set travaux_envisages = coalesce((
    select array_agg(x.code order by x.rang)
    from (
        select e.code, min(t.ord * 10 + e.sub) as rang
        from unnest(p.travaux_envisages) with ordinality as t(code, ord)
        cross join lateral unnest(
            case t.code
                when 'toiture' then array['charpente', 'couverture']
                when 'equipement_professionnel' then array[]::text[]
                else array[t.code]
            end
        ) with ordinality as e(code, sub)
        group by e.code
    ) x
), '{}')
where p.travaux_envisages && array['toiture', 'equipement_professionnel'];
