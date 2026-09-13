-- Troisième table de la surcouche d'EXPLOITATION du catalogue : le prédicat
-- d'une condition, remplaçable depuis /admin.
--
-- Même doctrine que `aides_retirees` et `faits_surcharges` (migration
-- 20260911201246) : `backend/data/` reste la vérité ÉDITORIALE, le loader ne
-- touche jamais cette table, et le moteur l'applique PAR-DESSUS le cache YAML
-- au moment de servir. Un prédicat corrigé durablement se reporte dans
-- `data/aides/<slug>.yaml`, puis la ligne se supprime depuis /admin — sinon
-- elle fige la version d'avant et la correction du YAML reste sans effet.
--
-- Le mandat est étroit, et il est énoncé côté applicatif
-- (`catalogue_admin.condition_modifiable`) : conditions `kind: user_fact` +
-- `effect: gate` portant sur un fait à options, prédicats de forme simple
-- (aucun combinateur). L'éditeur est un menu plus des cases à cocher, jamais
-- du JSON libre.
--
-- Aucune FK vers le catalogue : le YAML est la vérité et la base peut être en
-- retard sur lui. Une ligne devenue orpheline est ignorée avec un
-- avertissement plutôt que de casser un diagnostic.

create table public.conditions_predicats (
    aide_slug    text not null,
    condition_id text not null,
    -- Le prédicat SERVI à la place de celui du YAML. Forme simple :
    -- {"in": ["a","b"]}, {"eq": "a"}, {"neq": "a"}, {"not_in": [...]}.
    predicate    jsonb not null,

    -- ── Les trois témoins de péremption ─────────────────────────────────────
    -- Ils mémorisent ce qui a MOTIVÉ la décision humaine, pour la comparer à
    -- chaque passage et laisser l'alerte revenir d'elle-même. Patron repris de
    -- `traiter_acquittements` (scripts/veille_aides.py).

    -- Le texte de la condition au moment de la surcharge. S'il change dans le
    -- YAML, la décision a été prise sur une AUTRE condition que celle qu'on
    -- sert : la ligne est périmée et n'est plus appliquée. Stocké en clair et
    -- non en empreinte, parce que /admin doit AFFICHER l'ancien à côté du
    -- nouveau — c'est ce qui rend l'alerte actionnable.
    condition_text text not null,
    -- Un retypage vers un autre fait rendrait le prédicat absurde sans toucher
    -- au texte.
    fact_key       text not null,
    -- Le prédicat YAML au moment de la surcharge. Il ne PÉRIME pas la ligne,
    -- il la marque « à revoir » : le YAML a rattrapé, quelqu'un doit trancher.
    -- La surcharge continue de s'appliquer entre-temps — l'ignorer re-casserait
    -- en silence ce que l'administrateur avait réparé.
    predicate_origine jsonb not null,

    -- Pourquoi, pour l'autre fondateur qui verra la ligne dans /admin.
    motif       text null,
    modifie_par uuid null references public.users (id) on delete set null,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now(),

    primary key (aide_slug, condition_id),
    constraint conditions_predicats_objet
        check (jsonb_typeof(predicate) = 'object'),
    constraint conditions_predicats_origine_objet
        check (jsonb_typeof(predicate_origine) = 'object')
);

drop trigger if exists conditions_predicats_updated_at on public.conditions_predicats;
create trigger conditions_predicats_updated_at before update on public.conditions_predicats
    for each row execute function public.update_updated_at();

-- RLS sans aucune policy, comme les deux autres tables de la surcouche : seul
-- le service-role du backend lit et écrit ici, derrière `require_admin`. Les
-- grants sont retirés par surcroît — une table du catalogue n'a rien à faire
-- dans PostgREST.
alter table public.conditions_predicats enable row level security;
revoke all on public.conditions_predicats from anon, authenticated;
