-- Scission de la famille `tourisme_hebergement` en deux — 2026-09-22.
--
-- L'ancien code mettait dans le même sac un gîte et un sentier de randonnée.
-- Cocher la tuile ne disait donc rien de précis, et le moteur devait quand même
-- demander « créez-vous un hébergement touristique ? » juste après. Les deux
-- codes qui la remplacent sont assez étroits pour répondre à la place de
-- l'utilisateur (`FAITS_DEDUITS_VRAI_DES_FAMILLES`) :
--
--   `hebergement_touristique` — gîtes, chambres d'hôtes, hôtel, camping, hostel…
--   `tourisme_visite`         — sites de visite, itinérance, évènementiel.
--
-- TROIS temps, et l'ordre porte tout : DROP, puis UPDATE, puis ADD. Le CHECK en
-- place énumère les treize anciennes valeurs — il interdit donc les deux
-- nouvelles, et un UPDATE lancé avant le DROP échoue en 23514 sur sa propre
-- première ligne. (Première écriture de cette migration : l'UPDATE venait en
-- tête, au motif qu'il fallait « élargir avant de resserrer ». C'est l'inverse :
-- ici le resserrement est déjà là, c'est lui qu'on desserre d'abord.)
--
-- (a) DROP du CHECK existant. La table reste une poignée de millisecondes sans
-- contrainte, dans la transaction de la migration : rien d'autre n'écrit.
--
-- (b) Les lignes qui portent l'ancien code reçoivent les DEUX nouveaux. Élargir
-- ne coûte rien — `hors_famille` n'écarte que sur intersection vide, donc une
-- famille de plus ne masque jamais une aide — et de toute façon le prochain
-- `load_aides_yaml.py` réécrira le tag exact décidé dans les YAML. C'est un
-- filet pour l'intervalle entre la migration et le load, pas la vérité.
--
-- (c) ADD du CHECK à 14 valeurs, celles de `labels.FAMILLES_LABELS`, d'où
-- `aides_schema.FAMILLES` dérive et que `frontend/src/constants/familles.ts`
-- reproduit — trois lieux, trois tests qui les comparent
-- (`tests/test_familles.py`, `src/constants/__tests__/familles.test.ts`).
-- Pas d'`IF NOT EXISTS` sur le DROP+ADD : reposer la contrainte EST le but, et
-- la migration reste rejouable puisqu'elle la recrée toujours à l'identique.
--
-- ⚠ À APPLIQUER AVANT le `load_aides_yaml.py` qui suit le re-tag des aides :
-- sans elle, l'upsert des 44 fiches retaguées échoue sur le CHECK.

alter table public.aides_v3
    drop constraint if exists aides_v3_familles_check;

update public.aides_v3
   set familles = array_cat(
           array_remove(familles, 'tourisme_hebergement'),
           array['hebergement_touristique', 'tourisme_visite']
       )
 where 'tourisme_hebergement' = any(familles);

alter table public.aides_v3
    add constraint aides_v3_familles_check check (
        familles <@ array[
            'restauration_bati',
            'energie_climat',
            'eau_nature_domaine',
            'securite_risques',
            'parcs_jardins_paysages',
            'hebergement_touristique',
            'tourisme_visite',
            'activite_economique_lieu',
            'spectacles_manifestations',
            'vie_locale_associative',
            'mediation_numerique_expositions',
            'accessibilite_publics',
            'etudes_ingenierie',
            'labels_passerelles'
        ]::text[]
    );
