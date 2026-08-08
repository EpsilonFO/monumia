-- Facturation Stripe : déblocage « Dossier » par projet + abonnement compte.
--
-- Deux droits d'accès distincts, cumulables :
--   • monument_unlocks — un paiement unique débloque UN projet, pour toujours.
--   • subscriptions    — un abonnement actif débloque TOUS les projets du compte.
-- Le flag historique users.has_aides_access reste la porte de service : il
-- débloque tout, manuellement, sans passer par Stripe (comptes beta, démos).
--
-- Toutes ces tables sont écrites exclusivement par le webhook Stripe, côté
-- service-role. L'utilisateur n'a que le droit de lire ses propres lignes :
-- sans ça, un client pourrait s'auto-accorder un déblocage par un simple INSERT.

-- =============================================================================
-- 1. Rattachement du compte au client Stripe
-- =============================================================================
-- Conservé sur le user pour ne pas recréer un Customer à chaque paiement :
-- Stripe agrégerait sinon l'historique du même client sous plusieurs ids.
alter table public.users
    add column if not exists stripe_customer_id text;

create unique index if not exists users_stripe_customer_id_key
    on public.users (stripe_customer_id)
    where stripe_customer_id is not null;

-- Même verrouillage que has_aides_access : la colonne identifie un moyen de
-- paiement, la réécrire permettrait de se brancher sur le Customer d'un autre.
revoke update (stripe_customer_id) on public.users from authenticated;
revoke update (stripe_customer_id) on public.users from anon;

-- =============================================================================
-- 2. Déblocages « Dossier » — paiement unique, portée un projet
-- =============================================================================
create table if not exists public.monument_unlocks (
    id                          uuid not null default gen_random_uuid(),
    user_id                     uuid not null references public.users(id) on delete cascade,
    -- Nullable + set null : la suppression du projet ne doit pas effacer la
    -- trace comptable d'un paiement encaissé. L'accès tombe de lui-même,
    -- puisque plus aucun monument_id ne correspond.
    monument_id                 uuid null references public.monuments(id) on delete set null,
    stripe_checkout_session_id  text not null,
    stripe_payment_intent_id    text null,
    amount_cents                integer null,
    currency                    text not null default 'eur',
    created_at                  timestamptz not null default now(),
    constraint monument_unlocks_pkey primary key (id),
    -- Idempotence du webhook : Stripe peut livrer checkout.session.completed
    -- plusieurs fois pour la même session.
    constraint monument_unlocks_session_key unique (stripe_checkout_session_id)
);

-- Un seul déblocage payant par (compte, projet) : un double clic sur « Payer »
-- crée deux sessions Checkout, et la seconde ne doit pas encaisser deux fois.
-- Partiel car monument_id devient NULL quand le projet est supprimé.
create unique index if not exists monument_unlocks_user_monument_key
    on public.monument_unlocks (user_id, monument_id)
    where monument_id is not null;

create index if not exists idx_monument_unlocks_user
    on public.monument_unlocks (user_id);

alter table public.monument_unlocks enable row level security;

create policy "monument_unlocks: select own"
    on public.monument_unlocks
    as permissive
    for select
    to authenticated
    using (auth.uid() = user_id);

revoke insert, update, delete, truncate, references, trigger
    on public.monument_unlocks from anon, authenticated;

-- =============================================================================
-- 3. Abonnements — récurrent, portée compte entier
-- =============================================================================
-- Clé primaire = l'id d'abonnement Stripe, et non user_id : un compte qui
-- résilie puis se réabonne obtient un nouvel abonnement, et écraser l'ancien
-- effacerait l'historique dont dépend le support client.
create table if not exists public.subscriptions (
    stripe_subscription_id  text not null,
    user_id                 uuid not null references public.users(id) on delete cascade,
    stripe_customer_id      text not null,
    stripe_price_id         text null,
    -- Vocabulaire Stripe repris tel quel : incomplete, incomplete_expired,
    -- trialing, active, past_due, canceled, unpaid, paused.
    status                  text not null,
    current_period_end      timestamptz null,
    cancel_at_period_end    boolean not null default false,
    created_at              timestamptz not null default now(),
    updated_at              timestamptz not null default now(),
    constraint subscriptions_pkey primary key (stripe_subscription_id)
);

create index if not exists idx_subscriptions_user
    on public.subscriptions (user_id);

alter table public.subscriptions enable row level security;

create policy "subscriptions: select own"
    on public.subscriptions
    as permissive
    for select
    to authenticated
    using (auth.uid() = user_id);

revoke insert, update, delete, truncate, references, trigger
    on public.subscriptions from anon, authenticated;

-- =============================================================================
-- 4. Journal des événements webhook — idempotence
-- =============================================================================
-- Stripe garantit une livraison « au moins une fois » : le même événement peut
-- arriver deux fois (retry après timeout). L'insertion de l'id sert de verrou —
-- si elle échoue en doublon, l'événement a déjà été traité.
create table if not exists public.stripe_events (
    id           text not null,
    type         text not null,
    received_at  timestamptz not null default now(),
    constraint stripe_events_pkey primary key (id)
);

alter table public.stripe_events enable row level security;

-- Aucune policy : table strictement interne au webhook (service-role).
revoke select, insert, update, delete, truncate, references, trigger
    on public.stripe_events from anon, authenticated;
