-- Rappels par email : échéances qui approchent, et ouvertures de guichet.
--
-- Deux évènements calendaires méritent un email, et un seul les distingue mal :
--
--   * ÉCHÉANCE — une aide déjà identifiée sur un projet (« Éligible
--     maintenant », « À confirmer », « À débloquer ») dont la `date_limite`
--     tombe dans N jours. N est configurable par utilisateur, 30 par défaut.
--   * OUVERTURE — une aide qui attendait dans « Disponibles bientôt » et dont
--     la `date_ouverture` vient d'être franchie : elle bascule d'elle-même dans
--     l'un des trois seaux du haut, et l'email annonce ce basculement.
--
-- Le basculement lui-même ne demande aucune écriture : `disponibilite()` le
-- recalcule à chaque diagnostic à partir de la date du jour. Ce qui manque, et
-- que cette table apporte, c'est la MÉMOIRE de ce qui a déjà été annoncé — le
-- job tourne tous les matins et ne doit pas répéter le même rappel 30 jours
-- d'affilée.


-- ---------------------------------------------------------------------------
-- 1. Journal des rappels déjà envoyés
-- ---------------------------------------------------------------------------
create type public.aide_rappel_kind as enum ('echeance', 'ouverture');

create table public.aide_rappels_envoyes (
    id uuid not null default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    projet_id uuid not null references public.projets (id) on delete cascade,
    -- Slug du catalogue YAML, comme dossiers.aide_id et aide_suivis.aide_id :
    -- le moteur déterministe ne connaît que les slugs, pas les UUID aides_v3.
    aide_id text not null,
    kind public.aide_rappel_kind not null,
    -- Palier de rappel en jours (30, 7…) pour un rappel d'échéance ; null pour
    -- une ouverture, qui n'en a pas.
    palier_jours integer,
    -- La date ANNONCÉE : `date_limite` pour une échéance, `date_ouverture` pour
    -- une ouverture. Elle fait partie de la clé d'unicité, et c'est ce qui rend
    -- les dispositifs annuels reconduits corrects : la session 2027 d'une aide
    -- déclenche ses propres rappels sans être confondue avec celle de 2026.
    date_reference date not null,
    envoye_le timestamptz not null default now(),
    constraint aide_rappels_envoyes_pkey primary key (id),
    constraint aide_rappels_envoyes_palier_coherent check (
        (kind = 'echeance' and palier_jours is not null and palier_jours >= 0)
        or (kind = 'ouverture' and palier_jours is null)
    )
);

-- Unicité = la garantie « un rappel, une fois ». `palier_jours` étant nullable
-- pour les ouvertures, un index unique ordinaire ne suffirait pas (NULL n'est
-- jamais égal à NULL en SQL) : `nulls not distinct` le rend comparable.
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
-- 2. Préférences de rappel sur `users.notification_preferences`
-- ---------------------------------------------------------------------------
-- Trois clés s'ajoutent au jsonb existant :
--
--   rappelsEcheances    bool   — recevoir les rappels d'échéance
--   rappelsOuvertures   bool   — recevoir les annonces d'ouverture de guichet
--   rappelDelaisJours   int[]  — les paliers, en jours avant la date limite
--
-- `rappelDelaisJours` est une liste et non un entier : demander « 30 jours ET
-- 7 jours » est le besoin réel — un rappel pour s'organiser, un pour ne pas
-- oublier. Un seul palier reste le défaut.
alter table public.users
  alter column notification_preferences
  set default '{"dossierUpdates": true, "newAidesMatched": true, "urgentDeadlines": true, "emailNotifications": false, "rappelsEcheances": true, "rappelsOuvertures": true, "rappelDelaisJours": [30]}'::jsonb;

-- Backfill des comptes existants. `||` écrase, donc on ne fusionne que les
-- clés ABSENTES : un utilisateur qui aurait déjà réglé ses paliers les garde.
update public.users
set notification_preferences =
  '{"rappelsEcheances": true, "rappelsOuvertures": true, "rappelDelaisJours": [30]}'::jsonb
  || notification_preferences
where not (notification_preferences ? 'rappelDelaisJours');
