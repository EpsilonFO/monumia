-- Add a column to track aids imported from aides-territoires.beta.gouv.fr
-- Uses the slug from their API as a stable unique identifier for upsert logic.
alter table public.aides_v2
  add column if not exists source_at_slug text unique;

comment on column public.aides_v2.source_at_slug is
  'Slug from aides-territoires API — used to deduplicate weekly syncs';
