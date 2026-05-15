-- Enable Row Level Security on aides_v3.
-- Pattern miroir d'aides_v2 : table référentielle, lecture pour les utilisateurs
-- authentifiés, écritures réservées au service_role (qui bypass RLS).

alter table public.aides_v3 enable row level security;

drop policy if exists "aides_v3_read" on public.aides_v3;
create policy "aides_v3_read"
    on public.aides_v3
    as permissive
    for select
    to authenticated
    using (true);
