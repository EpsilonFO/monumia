-- Trois offres : Gratuit, Veille, Multi-monuments.
--
-- Ce qui change par rapport au modèle précédent (« Dossier » à l'unité +
-- « Abonnement » tout-accès) :
--
--   * le détail des aides n'est PLUS payant. L'offre gratuite le montre en
--     entier. Ce qui se vend désormais, ce sont les VOLUMES (monuments,
--     projets), le CALENDRIER (échéancier, aides à venir) et la VEILLE par
--     email. D'où la disparition de `users.has_aides_access` et de
--     `monument_unlocks`, tous deux au service du seul paywall « aides ».
--   * les deux offres payantes sont des abonnements, et l'une contient
--     l'autre : Multi-monuments ouvre tout ce que Veille ouvre. Il faut donc
--     savoir QUELLE offre porte un abonnement, ce que `stripe_price_id` ne dit
--     pas de façon lisible — d'où la colonne `plan`.
--
-- Aucun client n'a encore payé : les anciens droits sont coupés net plutôt que
-- repris. Un abonnement d'avant cette migration a `plan` à NULL, et le code
-- traite « plan inconnu » comme n'ouvrant rien (cf. services/offres.py).


-- ---------------------------------------------------------------------------
-- 1. Fin du paywall « détail des aides »
-- ---------------------------------------------------------------------------
-- Déblocage à l'unité : l'offre « Dossier » n'existe plus. La table entière
-- part, y compris sa trace comptable — elle n'a jamais encaissé une ligne.
drop table if exists public.monument_unlocks;

-- Octroi manuel du tout-accès (comptes beta, démos). Il ne débloquait que les
-- aides, qui sont maintenant gratuites : la colonne n'a plus d'objet. Ses
-- grants de colonne (revoke update, cf. 20260506120000 et 20260819063929)
-- tombent avec elle.
alter table public.users
    drop column if exists has_aides_access;


-- ---------------------------------------------------------------------------
-- 2. Quelle offre porte un abonnement
-- ---------------------------------------------------------------------------
-- Renseignée par le webhook depuis les métadonnées que NOUS posons à la
-- création de la session Checkout — jamais depuis un champ envoyé par
-- l'appelant (cf. routers/billing.py).
alter table public.subscriptions
    add column if not exists plan text;

comment on column public.subscriptions.plan is
    'Offre souscrite : veille | multi_monuments. NULL = abonnement antérieur '
    'aux trois offres, qui n''ouvre aucun droit.';

-- NULL reste accepté : c'est l'état des abonnements legacy, et il vaut « aucun
-- droit ». Ce que la contrainte interdit, c'est un plan inventé — un plan
-- inconnu passerait sinon silencieusement pour un droit valide le jour où le
-- code se mettrait à comparer autrement.
alter table public.subscriptions
    drop constraint if exists subscriptions_plan_connu;

alter table public.subscriptions
    add constraint subscriptions_plan_connu
    check (plan is null or plan in ('veille', 'multi_monuments'));

-- Le calcul des droits lit les abonnements ACTIFS d'un compte à chaque
-- diagnostic, chaque création de monument et chaque création de projet. La
-- recherche porte sur (user_id, status) : l'index sur user_id seul obligeait à
-- relire toutes les lignes d'un compte qui se réabonne.
create index if not exists idx_subscriptions_user_status
    on public.subscriptions (user_id, status);
