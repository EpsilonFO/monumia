ALTER TABLE public.aides_v3
ADD COLUMN IF NOT EXISTS created_at timestamptz not null default now(),
ADD COLUMN IF NOT EXISTS updated_at timestamptz not null default now();