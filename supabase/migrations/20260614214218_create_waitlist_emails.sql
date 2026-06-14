-- Waitlist : e-mails collectés sur la landing avant le lancement.
-- Écrite uniquement par le backend (client service-role, qui bypass la RLS).
-- RLS activée sans policy publique : ni anon ni authenticated ne peuvent lire
-- ni écrire la table directement.
create table if not exists public.waitlist_emails (
    id uuid not null default gen_random_uuid() primary key,
    email text not null,
    source text not null default 'landing',
    created_at timestamptz not null default now(),
    constraint waitlist_emails_email_key unique (email)
);

create index if not exists idx_waitlist_emails_created_at
    on public.waitlist_emails using btree (created_at desc);

alter table public.waitlist_emails enable row level security;
