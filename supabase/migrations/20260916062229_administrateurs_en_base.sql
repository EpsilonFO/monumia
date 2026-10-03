-- Les administrateurs du catalogue, en base plutôt que dans une variable
-- d'environnement.
--
-- `ADMIN_USER_IDS` reste lue, mais comme un SOCLE d'amorçage : c'est elle qui
-- ouvre la porte le jour où la table est vide (juste après cette migration, ou
-- sur un environnement neuf), et elle ne se gère pas depuis l'application. Les
-- administrateurs ajoutés depuis `/admin` vivent ici, où une ligne se lit avec
-- un email à côté plutôt qu'un UUID recopié à la main.
--
-- L'autorité reste `require_admin` ([backend/db.py]), qui interroge l'UNION des
-- deux : le socle ne se retire pas depuis l'application, le reste si.
--
-- Un administrateur détient par ailleurs l'offre Multi-monuments d'office, sans
-- ligne d'abonnement : c'est `stripe_billing.active_plans` qui l'ajoute, de
-- sorte que retirer quelqu'un de cette table lui reprenne aussi ce droit.

create table public.administrateurs (
    -- `on delete cascade` : un compte supprimé n'a plus rien à administrer, et
    -- une ligne orpheline rouvrirait la porte à un UUID recyclé.
    user_id    uuid primary key references public.users (id) on delete cascade,
    -- Pourquoi, pour l'autre fondateur qui verra la ligne dans /admin.
    motif      text null,
    ajoute_par uuid null references public.users (id) on delete set null,
    created_at timestamptz not null default now()
);

-- RLS sans aucune policy, comme les trois tables de la surcouche du catalogue :
-- seul le service-role du backend lit et écrit ici, derrière `require_admin`.
-- Les grants sont retirés par surcroît — la liste des administrateurs n'a rien
-- à faire dans PostgREST, et surtout pas en écriture.
alter table public.administrateurs enable row level security;
revoke all on public.administrateurs from anon, authenticated;
