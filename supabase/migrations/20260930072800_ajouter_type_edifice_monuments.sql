-- Type d'édifice du monument, et ses deux précisions.
--
-- Une quinzaine de faits du questionnaire (backend/data/facts.yaml) décrivent
-- la NATURE du bien : « l'édifice est-il une église ou une chapelle ? »,
-- « un édifice cultuel ? », « un monument aux morts ? », « représentatif de
-- l'histoire et de la culture juives ? »… Chacun se posait à part, y compris au
-- propriétaire d'un lavoir. Le type, saisi une fois sur la fiche, y répond
-- d'avance : le moteur le lit par `auto_source` (eligibility_engine,
-- DEDUCTIONS_TYPE_EDIFICE). La réponse de l'utilisateur prime toujours.
--
-- Les trois colonnes sont NULLABLES : les fiches existantes n'ont pas de type,
-- et un type absent ne déduit rien (la question reste posée, fail-closed).
--
-- Les précisions n'ont de sens que pour certains types (liste dans
-- backend/labels.py, TYPES_AVEC_AFFECTATION_CULTE et
-- TYPES_AVEC_ARCHITECTURE_ROMANE). Elles ne sont pas contraintes ici : le
-- router les vide quand le type change, et le moteur ne les lit que sous un
-- type où elles s'appliquent.
--
-- Liste fermée à garder d'accord avec `TYPE_EDIFICE_LABELS` (backend/labels.py)
-- et `TYPES_EDIFICE` (frontend/src/constants/monument-options.ts) :
-- tests/test_type_edifice.py compare les trois.

alter table public.monuments
    add column if not exists type_edifice text,
    add column if not exists affecte_au_culte boolean,
    add column if not exists architecture_romane boolean;

alter table public.monuments
    drop constraint if exists monuments_type_edifice_check;

alter table public.monuments
    add constraint monuments_type_edifice_check check (
        type_edifice is null
        or type_edifice in (
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
        )
    );

comment on column public.monuments.type_edifice is
    'Nature du bien (backend/labels.py, TYPE_EDIFICE_LABELS). Répond d''avance aux faits constatifs du questionnaire.';
comment on column public.monuments.affecte_au_culte is
    'Édifice religieux toujours affecté au culte (true) ou désaffecté (false). Null : non renseigné.';
comment on column public.monuments.architecture_romane is
    'Architecture romane, en tout ou en partie (true), ou non (false). Null : non renseigné.';
