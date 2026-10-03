-- Rappels par email sur les aides (scripts/rappels_aides.py, cron quotidien).
--
-- Trois évènements valent un email, réservés aux offres Veille et
-- Multi-monuments (`peut_recevoir_rappels`) :
--
--   * ÉCHÉANCE — une aide à portée d'un projet (« Éligible maintenant », « À
--     confirmer », « À débloquer ») dont la `date_limite` tombe dans N jours.
--     N est réglable par utilisateur, 30 par défaut.
--   * OUVERTURE — une aide fermée (« Disponibles bientôt ») qui devient
--     déposable : `date_ouverture` atteinte, ou nouvelle session posée par la
--     veille.
--   * NOUVELLE — une aide qui entre au catalogue guichet ouvert, annoncée à
--     chaque projet dont elle passe les critères automatiques sans qu'une
--     réponse déjà donnée l'écarte.
--
-- Rien de tout cela ne s'écrit sur l'aide elle-même : `disponibilite()`
-- recalcule la fenêtre de candidature à chaque diagnostic. Ce que la base
-- apporte, c'est de la MÉMOIRE : ce qui a déjà été annoncé (1), et l'état du
-- catalogue la veille, sans lequel « vient d'ouvrir » et « vient d'arriver »
-- ne se distinguent pas de « ouvert depuis toujours » (2).
--
-- Remplace la migration 20260828152623 du même nom, jamais appliquée (restée
-- dans un worktree) : son horodatage précédait des migrations déjà poussées.


-- ---------------------------------------------------------------------------
-- 1. Journal des rappels déjà envoyés
-- ---------------------------------------------------------------------------
create type public.aide_rappel_kind as enum ('echeance', 'ouverture', 'nouvelle');

create table public.aide_rappels_envoyes (
    id uuid not null default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    projet_id uuid not null references public.projets (id) on delete cascade,
    -- Slug du catalogue YAML, comme dossiers.aide_id et aide_suivis.aide_id :
    -- le moteur déterministe ne connaît que les slugs, pas les UUID aides_v3.
    aide_id text not null,
    kind public.aide_rappel_kind not null,
    -- Palier de rappel en jours (30, 7…) pour une échéance ; null sinon.
    palier_jours integer,
    -- La date ANNONCÉE : `date_limite` pour une échéance, le jour où l'aide est
    -- devenue disponible sinon. Elle fait partie de la clé d'unicité, et c'est
    -- ce qui rend les dispositifs annuels corrects : la session 2027 d'une aide
    -- déclenche ses propres rappels sans être confondue avec celle de 2026.
    date_reference date not null,
    envoye_le timestamptz not null default now(),
    constraint aide_rappels_envoyes_pkey primary key (id),
    constraint aide_rappels_envoyes_palier_coherent check (
        (kind = 'echeance' and palier_jours is not null and palier_jours >= 0)
        or (kind <> 'echeance' and palier_jours is null)
    )
);

-- Unicité = la garantie « un rappel, une fois ». `palier_jours` étant nullable,
-- un index unique ordinaire ne suffirait pas (NULL n'est jamais égal à NULL en
-- SQL) : `nulls not distinct` le rend comparable.
create unique index aide_rappels_envoyes_unique
  on public.aide_rappels_envoyes (user_id, projet_id, aide_id, kind, palier_jours, date_reference)
  nulls not distinct;

create index idx_aide_rappels_user on public.aide_rappels_envoyes using btree (user_id);
create index idx_aide_rappels_projet on public.aide_rappels_envoyes using btree (projet_id);

-- Table de service : écrite par le job (service-role), jamais lue par le front.
-- RLS activé et aucune policy = personne d'autre que le service-role n'y touche.
alter table public.aide_rappels_envoyes enable row level security;
revoke all on public.aide_rappels_envoyes from anon, authenticated;


-- ---------------------------------------------------------------------------
-- 2. Instantané du catalogue
-- ---------------------------------------------------------------------------
-- Une ligne par aide servie, mise à jour chaque matin par le job. Le premier
-- passage remplit la table sans rien annoncer (`ouverte_depuis` reste null).
create table public.aides_veille_etat (
    aide_id text not null,
    -- Guichet ouvert au dernier passage (`disponibilite() = 'maintenant'`).
    ouverte boolean not null,
    -- Premier jour où le job a vu l'aide dans le catalogue servi.
    entree_le date not null,
    -- Jour où le job l'a vue devenir disponible ; null si elle est fermée, ou
    -- si elle l'était déjà au premier passage. `ouverte_depuis = entree_le`
    -- distingue une aide NOUVELLE d'une RÉOUVERTURE.
    ouverte_depuis date,
    maj_le timestamptz not null default now(),
    constraint aides_veille_etat_pkey primary key (aide_id)
);

alter table public.aides_veille_etat enable row level security;
revoke all on public.aides_veille_etat from anon, authenticated;


-- ---------------------------------------------------------------------------
-- 3. Préférences de rappel sur `users.notification_preferences`
-- ---------------------------------------------------------------------------
-- Trois clés s'ajoutent au jsonb existant :
--
--   rappelsEcheances    bool   — recevoir les rappels d'échéance
--   rappelsOuvertures   bool   — recevoir les aides qui deviennent disponibles
--                                (nouvelles au catalogue et réouvertures)
--   rappelDelaisJours   int[]  — les paliers, en jours avant la date limite
--
-- `rappelDelaisJours` est une liste et non un entier : demander « 30 jours ET
-- 7 jours » est le besoin réel — un rappel pour s'organiser, un pour ne pas
-- oublier. Un seul palier reste le défaut.
alter table public.users
  alter column notification_preferences
  set default '{"dossierUpdates": true, "newAidesMatched": true, "urgentDeadlines": true, "emailNotifications": false, "rappelsEcheances": true, "rappelsOuvertures": true, "rappelDelaisJours": [30]}'::jsonb;

-- Backfill des comptes existants. `||` écrase à droite, donc les clés déjà
-- posées par l'utilisateur (à droite) l'emportent sur les défauts.
update public.users
set notification_preferences =
  '{"rappelsEcheances": true, "rappelsOuvertures": true, "rappelDelaisJours": [30]}'::jsonb
  || notification_preferences
where not (notification_preferences ? 'rappelDelaisJours');
