-- Rôle Postgres en lecture seule pour les serveurs MCP monumia-prod et monumia-beta.
--
-- À coller dans le SQL Editor de Supabase Studio, une fois sur chaque projet.
-- Rejouable sans risque : le script remet le rôle et ses droits dans l'état
-- décrit ici. Ce n'est volontairement PAS une migration, pour qu'il ne parte ni
-- en local ni dans deploy.sh. Le mot de passe n'est pas dans ce fichier : il se
-- pose à part (cf. README.md).
--
-- C'est ce rôle qui garantit la lecture seule, pas le serveur MCP : il n'a aucun
-- droit d'écriture, nulle part. default_transaction_read_only n'est qu'un
-- confort (une session peut le désactiver) ; la frontière, ce sont les GRANT.

begin;

-- ── Le rôle ───────────────────────────────────────────────────────────────
-- BYPASSRLS : sans lui, les tables sous RLS rendraient zéro ligne (le backend
-- lit en service-role). Il ne donne aucun droit d'écriture.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'mcp_lecture') then
    create role mcp_lecture
      login noinherit nocreatedb nocreaterole noreplication bypassrls
      connection limit 3;
  else
    alter role mcp_lecture
      login noinherit nocreatedb nocreaterole noreplication bypassrls
      connection limit 3;
  end if;
end $$;

-- Garde-fous de charge : une requête lourde lancée par un agent ne doit pas
-- tenir la prod.
alter role mcp_lecture set statement_timeout = '15s';
alter role mcp_lecture set idle_in_transaction_session_timeout = '30s';
alter role mcp_lecture set default_transaction_read_only = on;

-- ── Schéma public : SELECT seulement ──────────────────────────────────────
grant usage on schema public to mcp_lecture;
grant select on all tables in schema public to mcp_lecture;

-- Les tables des migrations futures (créées par postgres) seront lisibles
-- sans repasser ce script.
alter default privileges for role postgres in schema public
  grant select on tables to mcp_lecture;

-- ── auth.users : une vue filtrée, jamais la table ─────────────────────────
-- La table porte encrypted_password et les jetons de confirmation et de
-- récupération. La vue appartient à postgres et s'exécute avec ses droits
-- (pas de security_invoker) : c'est pourquoi elle vit dans un schéma que
-- PostgREST n'expose pas et qu'anon/authenticated ne peuvent pas traverser.
-- Posée dans public, elle aurait ouvert auth.users à l'API.
create schema if not exists lecture;
revoke all on schema lecture from public, anon, authenticated, service_role;
grant usage on schema lecture to mcp_lecture;

create or replace view lecture.auth_users with (security_barrier) as
select
  id,
  email,
  created_at,
  updated_at,
  invited_at,
  email_confirmed_at,
  last_sign_in_at,
  banned_until,
  deleted_at,
  is_anonymous,
  is_sso_user,
  raw_app_meta_data
from auth.users;

revoke all on lecture.auth_users from public, anon, authenticated, service_role;
grant select on lecture.auth_users to mcp_lecture;

commit;

-- Ensuite, à la main et une seule fois par environnement (un mot de passe
-- différent pour la prod et pour la beta) :
--
--   alter role mcp_lecture password '<mot de passe généré>';
