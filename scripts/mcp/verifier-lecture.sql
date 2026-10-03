-- Preuve que mcp_lecture ne peut rien écrire. À lancer CONNECTÉ EN mcp_lecture :
--
--   psql "$(security find-generic-password -s monumia-mcp-prod -w)" -f scripts/mcp/verifier-lecture.sql
--
-- Chaque contrôle affiche « OK » en NOTICE ou « ECHEC » en WARNING. Les
-- fonctions SECURITY DEFINER sont listées pour relecture, sans verdict.
-- Rien n'est écrit : les tentatives d'écriture visent zéro ligne et tournent
-- dans une transaction annulée.

\set ON_ERROR_STOP on
\set QUIET on

do $$
begin
  if current_user <> 'mcp_lecture' then
    raise exception 'Connecté en %, pas en mcp_lecture : le contrôle ne prouverait rien.', current_user;
  end if;
end $$;

\echo
\echo '── Attributs du rôle'
do $$
declare r pg_roles%rowtype;
begin
  select * into r from pg_roles where rolname = current_user;
  if r.rolsuper or r.rolcreaterole or r.rolcreatedb or r.rolreplication then
    raise warning 'ECHEC : attributs du rôle trop larges (super=%, createrole=%, createdb=%, replication=%)',
      r.rolsuper, r.rolcreaterole, r.rolcreatedb, r.rolreplication;
  else
    raise notice 'OK : ni superuser, ni createrole, ni createdb, ni replication';
  end if;
  if exists (select 1 from pg_auth_members where member = r.oid) then
    raise warning 'ECHEC : mcp_lecture est membre de : %',
      (select string_agg(roleid::regrole::text, ', ') from pg_auth_members where member = r.oid);
  else
    raise notice 'OK : membre d''aucun rôle';
  end if;
  if not r.rolbypassrls then
    raise warning 'ECHEC : pas de BYPASSRLS, les tables sous RLS rendront zéro ligne';
  end if;
end $$;

\echo
\echo '── Droits d''écriture sur les tables, tous schémas'
do $$
declare n int; liste text;
begin
  select count(*), string_agg(format('%I.%I (%s)', ns.nspname, c.relname, p.priv), ', ')
    into n, liste
  from pg_class c
  join pg_namespace ns on ns.oid = c.relnamespace
  cross join unnest(array['INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER']) as p(priv)
  where c.relkind in ('r', 'p', 'v', 'm', 'f')
    and ns.nspname not in ('pg_catalog', 'information_schema')
    and ns.nspname not like 'pg\_toast%'
    and ns.nspname not like 'pg\_temp%'
    and (has_table_privilege(c.oid, p.priv)
         or (p.priv in ('INSERT', 'UPDATE') and has_any_column_privilege(c.oid, p.priv)));
  if n > 0 then
    raise warning 'ECHEC : % droit(s) d''écriture : %', n, liste;
  else
    raise notice 'OK : aucun droit d''écriture sur aucune table';
  end if;
end $$;

\echo
\echo '── Droits de création (schémas, base)'
do $$
declare liste text;
begin
  select string_agg(nspname, ', ') into liste
  from pg_namespace
  where has_schema_privilege(oid, 'CREATE') and nspname not like 'pg\_temp%' and nspname not like 'pg\_toast\_temp%';
  if liste is not null then
    raise warning 'ECHEC : CREATE permis dans : %', liste;
  else
    raise notice 'OK : CREATE refusé dans tous les schémas';
  end if;
  if has_database_privilege(current_database(), 'CREATE') then
    raise warning 'ECHEC : CREATE permis sur la base';
  else
    raise notice 'OK : CREATE refusé sur la base';
  end if;
end $$;

\echo
\echo '── Tables sensibles hors d''atteinte'
do $$
declare t text;
begin
  foreach t in array array['auth.users', 'auth.sessions', 'auth.refresh_tokens', 'vault.secrets', 'vault.decrypted_secrets', 'storage.objects'] loop
    -- Pas to_regclass : il lève une erreur sur un schéma non traversable.
    if not exists (select 1 from pg_class c join pg_namespace ns on ns.oid = c.relnamespace
                   where ns.nspname || '.' || c.relname = t) then
      raise notice 'OK : % n''existe pas ici', t;
      continue;
    end if;
    begin
      execute format('select 1 from %s limit 1', t);
      raise warning 'ECHEC : % est lisible', t;
    exception when insufficient_privilege then
      raise notice 'OK : % refusée', t;
    end;
  end loop;
end $$;

\echo
\echo '── Vue lecture.auth_users'
do $$
declare n bigint;
begin
  select count(*) into n from lecture.auth_users;
  raise notice 'OK : lecture.auth_users lisible (% comptes)', n;
  begin
    execute 'select encrypted_password from lecture.auth_users limit 1';
    raise warning 'ECHEC : encrypted_password visible dans la vue';
  exception when undefined_column then
    raise notice 'OK : encrypted_password absent de la vue';
  end;
  if exists (select 1 from information_schema.columns
             where table_schema = 'lecture' and table_name = 'auth_users' and column_name like '%token%') then
    raise warning 'ECHEC : une colonne *token* est visible dans la vue';
  else
    raise notice 'OK : aucune colonne *token* dans la vue';
  end if;
end $$;

\echo
\echo '── Tentatives d''écriture, transaction forcée en READ WRITE'
-- On lève la lecture seule de session pour prouver que ce sont les GRANT qui
-- refusent, pas default_transaction_read_only. Les requêtes visent zéro ligne
-- (where false) et la transaction est annulée.
begin transaction read write;
do $$
declare
  t record;
  essai text;
  passees text := '';
  douteux text := '';
  n int := 0;
begin
  for t in
    select c.oid::regclass as rel,
           (select quote_ident(attname) from pg_attribute
             where attrelid = c.oid and attnum > 0 and not attisdropped
             order by attnum limit 1) as col
    from pg_class c join pg_namespace ns on ns.oid = c.relnamespace
    where ns.nspname = 'public' and c.relkind in ('r', 'p')
  loop
    n := n + 1;
    foreach essai in array array[
      format('insert into %s select * from %s where false', t.rel, t.rel),
      format('update %s set %s = %s where false', t.rel, t.col, t.col),
      format('delete from %s where false', t.rel)
    ] loop
      begin
        execute essai;
        passees := passees || essai || '; ';
      exception
        when insufficient_privilege then
          null;
        when others then
          -- Erreur levée avant le contrôle des droits (colonne générée…) :
          -- l'essai ne prouve rien, le contrôle par has_table_privilege tient.
          douteux := douteux || essai || ' [' || sqlerrm || ']; ';
      end;
    end loop;
  end loop;
  if douteux <> '' then
    raise notice 'Essais sans verdict : %', douteux;
  end if;
  if passees <> '' then
    raise warning 'ECHEC : écritures acceptées : %', passees;
  else
    raise notice 'OK : aucune écriture acceptée sur les % tables de public', n;
  end if;
end $$;
rollback;

\echo
\echo '── Réglages de session'
select current_setting('statement_timeout') as statement_timeout,
       current_setting('idle_in_transaction_session_timeout') as idle_in_transaction_session_timeout,
       current_setting('default_transaction_read_only') as default_transaction_read_only;

\echo '── Fonctions SECURITY DEFINER exécutables (à relire : seul chemin d''écriture indirect)'
\echo '   Une fonction de public qui écrit serait un problème ; celles des extensions Supabase'
\echo '   (graphql, etc.) sont attendues.'
select n.nspname as schema, p.proname as fonction, pg_get_userbyid(p.proowner) as proprietaire
from pg_proc p join pg_namespace n on n.oid = p.pronamespace
where p.prosecdef and has_function_privilege(p.oid, 'EXECUTE')
order by 1, 2;
