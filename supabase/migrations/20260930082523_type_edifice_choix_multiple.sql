-- Type d'édifice en CHOIX MULTIPLE.
--
-- Un domaine réunit souvent plusieurs édifices : un château, sa chapelle, son
-- pigeonnier. `monuments.type_edifice` passe donc de `text` à `text[]`. La
-- colonne a été posée par 20260930072800 (même jour) : les valeurs déjà écrites
-- deviennent un tableau d'un élément.
--
-- Le moteur déduit un fait des types cochés à l'UNANIMITÉ
-- (eligibility_engine, DEDUCTIONS_TYPE_EDIFICE) : un type qui ne tranche pas
-- suffit à laisser la question posée.
--
-- Un tableau vide n'a pas de sens (le router le normalise en NULL) : la
-- contrainte le refuse. Liste fermée à garder d'accord avec
-- `TYPE_EDIFICE_LABELS` (backend/labels.py) et `TYPES_EDIFICE`
-- (frontend/src/constants/monument-options.ts) : tests/test_type_edifice.py
-- compare les trois, sur la migration la plus récente qui pose la contrainte.

alter table public.monuments
    drop constraint if exists monuments_type_edifice_check;

alter table public.monuments
    alter column type_edifice type text[]
    using case when type_edifice is null then null else array[type_edifice] end;

alter table public.monuments
    add constraint monuments_type_edifice_check check (
        type_edifice is null
        or (
            cardinality(type_edifice) > 0
            and type_edifice <@ array[
                'eglise',
                'chapelle',
                'abbaye_couvent',
                'temple',
                'synagogue',
                'croix_calvaire',
                'autre_religieux',
                'chateau',
                'manoir_demeure',
                'hotel_particulier',
                'maison',
                'edifice_public',
                'hopital',
                'halle',
                'patrimoine_industriel',
                'ferme',
                'moulin',
                'lavoir_fontaine',
                'pigeonnier',
                'petit_patrimoine',
                'fortification',
                'pont',
                'jardin',
                'site_archeologique',
                'monument_aux_morts',
                'monument_commemoratif',
                'autre'
            ]::text[]
        )
    );

comment on column public.monuments.type_edifice is
    'Natures du bien, plusieurs possibles (backend/labels.py, TYPE_EDIFICE_LABELS). Répondent d''avance, à l''unanimité, aux faits constatifs du questionnaire.';
