-- Policies RLS du bucket privé `documents` (photos de monument ET pièces jointes).
--
-- Elles n'avaient jamais été écrites en migration : posées à la main dans le
-- dashboard sur la prod, et présentes dans le volume local (jamais
-- réinitialisé), elles manquaient donc à tout projet Supabase créé depuis —
-- d'où l'upload qui échoue en beta sur « new row violates row-level security
-- policy » alors qu'il passe en local et en prod.
--
-- Le client ne fait qu'INSÉRER, sous son propre dossier `<user_id>/`
-- (`uploadToStorage`, upsert désactivé). La LECTURE et la SUPPRESSION passent
-- toujours par le service role côté backend (liens signés de `sign_photos` et
-- `documents.py`, effacement de `_remove_from_storage`) : c'est ce qui permet à
-- TOUT membre du monument de voir une photo déposée par un autre. Les policies
-- select/delete ci-dessous ne servent donc que le dépositaire lui-même, et
-- élargir leur portée n'ouvrirait rien de plus au reste de l'équipe.

insert into storage.buckets (id, name, public)
values ('documents', 'documents', false)
on conflict (id) do nothing;

-- Noms hérités des créations manuelles (prod et local), retirés pour ne pas
-- empiler deux fois la même règle là où ils existent déjà.
drop policy if exists "Users can upload their own documents" on storage.objects;
drop policy if exists "Users can read their own documents" on storage.objects;
drop policy if exists "Users can delete their own documents" on storage.objects;
drop policy if exists "documents_user_insert" on storage.objects;
drop policy if exists "documents_user_select" on storage.objects;
drop policy if exists "documents_user_delete" on storage.objects;

create policy "documents_user_insert"
  on storage.objects
  for insert
  to authenticated
  with check (
    bucket_id = 'documents'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

create policy "documents_user_select"
  on storage.objects
  for select
  to authenticated
  using (
    bucket_id = 'documents'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

create policy "documents_user_delete"
  on storage.objects
  for delete
  to authenticated
  using (
    bucket_id = 'documents'
    and (storage.foldername(name))[1] = auth.uid()::text
  );
