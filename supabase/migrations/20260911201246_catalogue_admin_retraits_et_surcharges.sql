-- Surcouche d'EXPLOITATION du catalogue, administrée depuis /admin.
--
-- `backend/data/` reste la source de vérité éditoriale : ces deux tables ne
-- sont jamais touchées par `load_aides_yaml.py`, et le moteur les applique
-- PAR-DESSUS les YAML au moment de servir. Elles répondent à un besoin qui ne
-- peut pas attendre un commit et un déploiement : retirer du catalogue une
-- aide qui s'avère fausse, corriger la formulation d'une question du QCM.
--
-- Un retrait ou une reformulation DURABLE se reporte ensuite dans les YAML
-- (archivage de l'aide, correction de `facts.yaml`), puis se rétablit ici.
--
-- Aucune FK vers `aides_v3.slug` ni vers une table de faits : le YAML est la
-- vérité et la base peut être en retard sur lui. La validation est
-- applicative (`services/catalogue_admin.py`), et une ligne devenue orpheline
-- est ignorée avec un avertissement plutôt que de casser un diagnostic.

create table public.aides_retirees (
    slug        text primary key,
    -- Pourquoi, pour l'autre fondateur qui verra la ligne dans /admin.
    motif       text null,
    retiree_par uuid null references public.users (id) on delete set null,
    created_at  timestamptz not null default now()
);

create table public.faits_surcharges (
    fact_key    text primary key,
    question    text null,
    help        text null,
    -- Liste COMPLÈTE effective des réponses possibles [{id, label, unknown}] :
    -- elle REMPLACE `fact.options`, elle ne s'y ajoute pas. Les ids des
    -- options existantes restent figés (les prédicats des aides les citent) ;
    -- un id nouveau n'apparaît qu'avec une réponse nouvelle.
    options     jsonb null,
    modifie_par uuid null references public.users (id) on delete set null,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now(),
    -- Une ligne qui ne surcharge rien n'a pas de sens : /admin la supprime au
    -- lieu de l'écrire.
    constraint faits_surcharges_non_vide
        check (question is not null or help is not null or options is not null),
    constraint faits_surcharges_options_liste
        check (options is null or jsonb_typeof(options) = 'array')
);

drop trigger if exists faits_surcharges_updated_at on public.faits_surcharges;
create trigger faits_surcharges_updated_at before update on public.faits_surcharges
    for each row execute function public.update_updated_at();

-- RLS sans aucune policy, comme `project_members` : seul le service-role du
-- backend lit et écrit ici, derrière `require_admin`. Les grants sont retirés
-- par surcroît — une table du catalogue n'a rien à faire dans PostgREST.
alter table public.aides_retirees enable row level security;
alter table public.faits_surcharges enable row level security;
revoke all on public.aides_retirees from anon, authenticated;
revoke all on public.faits_surcharges from anon, authenticated;
