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
-- Deux temps, dans cet ordre : élargir les lignes AVANT de resserrer le CHECK,
-- sinon la contrainte rejetterait les lignes qu'elle doit encore accepter.
--
-- (a) Les lignes qui portent l'ancien code reçoivent les DEUX nouveaux. Élargir
-- ne coûte rien — `hors_famille` n'écarte que sur intersection vide, donc une
-- famille de plus ne masque jamais une aide — et de toute façon le prochain
-- `load_aides_yaml.py` réécrira le tag exact décidé dans les YAML. C'est un
-- filet pour l'intervalle entre la migration et le load, pas la vérité.
--
-- (b) Le CHECK est REPOSÉ (drop + add, pas `IF NOT EXISTS`) : il existe déjà
-- avec les treize anciennes valeurs, et le laisser en place refuserait les
-- deux nouvelles. Ses 14 valeurs sont celles de `labels.FAMILLES_LABELS`, d'où
-- `aides_schema.FAMILLES` dérive et que `frontend/src/constants/familles.ts`
-- reproduit — trois lieux, trois tests qui les comparent
-- (`tests/test_familles.py`, `src/constants/__tests__/familles.test.ts`).
--
-- ⚠ À APPLIQUER AVANT le `load_aides_yaml.py` qui suit le re-tag des aides :
-- sans elle, l'upsert des 44 fiches retaguées échoue sur le CHECK.

update public.aides_v3
   set familles = array_cat(
           array_remove(familles, 'tourisme_hebergement'),
           array['hebergement_touristique', 'tourisme_visite']
       )
 where 'tourisme_hebergement' = any(familles);

alter table public.aides_v3
    drop constraint if exists aides_v3_familles_check;

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
