ALTER TABLE public.aides_v3
ADD COLUMN created_at timestamptz not null default now(),
ADD COLUMN updated_at timestamptz not null default now();