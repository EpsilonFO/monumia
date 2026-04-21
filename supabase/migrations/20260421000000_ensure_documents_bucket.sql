-- Ensure the `documents` storage bucket exists locally.
-- In production it was created manually; locally it's only in seed.sql and
-- gets dropped by `supabase db reset` without re-seeding.
insert into storage.buckets (id, name, public)
values ('documents', 'documents', false)
on conflict (id) do nothing;
