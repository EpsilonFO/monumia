-- Security hardening migration.
-- Addresses: world-readable storage bucket, privilege escalation via UPDATE,
-- mutable user_id columns, merimee_buildings open INSERT, missing
-- monument-ownership checks on diagnostics/dossiers INSERTs.

-- =============================================================================
-- 1. Storage: drop world-readable policy on documents bucket
-- =============================================================================
drop policy if exists "documents_public_read" on storage.objects;

-- =============================================================================
-- 2. users: lock privilege columns and add WITH CHECK
-- =============================================================================
drop policy if exists "users: update own" on public.users;

create policy "users: update own"
  on public.users
  as permissive
  for update
  to authenticated
  using (auth.uid() = id)
  with check (auth.uid() = id);

-- Prevent self-elevation of feature flags / segment / email at column-grant level.
revoke update (has_aides_access, segment, email) on public.users from authenticated;
revoke update (has_aides_access, segment, email) on public.users from anon;

-- =============================================================================
-- 3. Add WITH CHECK + immutable user_id on every owner table
-- =============================================================================

-- dossiers
drop policy if exists "dossiers: update own" on public.dossiers;
create policy "dossiers: update own"
  on public.dossiers
  as permissive
  for update
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- documents
drop policy if exists "documents: update own" on public.documents;
create policy "documents: update own"
  on public.documents
  as permissive
  for update
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- monuments
drop policy if exists "monuments: update own" on public.monuments;
create policy "monuments: update own"
  on public.monuments
  as permissive
  for update
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- notifications
drop policy if exists "notifications: update own" on public.notifications;
create policy "notifications: update own"
  on public.notifications
  as permissive
  for update
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- prospects (uses btp_user_id)
drop policy if exists "prospects_update" on public.prospects;
create policy "prospects_update"
  on public.prospects
  as permissive
  for update
  to authenticated
  using (auth.uid() = btp_user_id)
  with check (auth.uid() = btp_user_id);

-- =============================================================================
-- 4. Defense-in-depth: trigger preventing user_id reassignment on owner tables
-- =============================================================================
create or replace function public.prevent_owner_change()
returns trigger
language plpgsql
as $$
begin
  if new.user_id is distinct from old.user_id then
    raise exception 'user_id is immutable';
  end if;
  return new;
end
$$;

create or replace function public.prevent_btp_owner_change()
returns trigger
language plpgsql
as $$
begin
  if new.btp_user_id is distinct from old.btp_user_id then
    raise exception 'btp_user_id is immutable';
  end if;
  return new;
end
$$;

drop trigger if exists lock_owner on public.dossiers;
create trigger lock_owner before update on public.dossiers
  for each row execute function public.prevent_owner_change();

drop trigger if exists lock_owner on public.documents;
create trigger lock_owner before update on public.documents
  for each row execute function public.prevent_owner_change();

drop trigger if exists lock_owner on public.monuments;
create trigger lock_owner before update on public.monuments
  for each row execute function public.prevent_owner_change();

drop trigger if exists lock_owner on public.notifications;
create trigger lock_owner before update on public.notifications
  for each row execute function public.prevent_owner_change();

drop trigger if exists lock_owner on public.diagnostics;
create trigger lock_owner before update on public.diagnostics
  for each row execute function public.prevent_owner_change();

drop trigger if exists lock_owner on public.prospects;
create trigger lock_owner before update on public.prospects
  for each row execute function public.prevent_btp_owner_change();

-- =============================================================================
-- 5. Tighten INSERT policies to verify monument ownership
-- =============================================================================
drop policy if exists "Users can insert their own diagnostics" on public.diagnostics;
create policy "Users can insert their own diagnostics"
  on public.diagnostics
  as permissive
  for insert
  to authenticated
  with check (
    auth.uid() = user_id
    and exists (
      select 1 from public.monuments m
      where m.id = monument_id and m.user_id = auth.uid()
    )
  );

drop policy if exists "dossiers: insert own" on public.dossiers;
create policy "dossiers: insert own"
  on public.dossiers
  as permissive
  for insert
  to authenticated
  with check (
    auth.uid() = user_id
    and exists (
      select 1 from public.monuments m
      where m.id = monument_id and m.user_id = auth.uid()
    )
  );

-- =============================================================================
-- 6. merimee_buildings: drop authenticated INSERT and revoke DML from anon/auth
-- =============================================================================
drop policy if exists "Enable insert for authenticated users only" on public.merimee_buildings;

revoke insert, update, delete, truncate, references, trigger
  on public.merimee_buildings from anon, authenticated;

-- Catalogue tables: revoke writes from anon/authenticated. Service role keeps full access.
revoke insert, update, delete, truncate, references, trigger
  on public.aides_v3,
     public.aides_departements,
     public.aides_etats_conservation,
     public.aides_proprietaires,
     public.aides_protections,
     public.aides_regions,
     public.aides_segments,
     public.aides_travaux,
     public.ref_etats_conservation,
     public.ref_proprietaires,
     public.ref_protections,
     public.ref_segments,
     public.ref_travaux,
     public.communes,
     public.communes_historique
  from anon, authenticated;

-- =============================================================================
-- 7. Drop duplicate storage SELECT policy left over from earlier migration
-- =============================================================================
drop policy if exists "Users can read their own documents flreew_0" on storage.objects;
