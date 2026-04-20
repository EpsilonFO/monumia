create table if not exists public.communes_historique (
    ancien_code_insee text primary key,
    nouveau_code_insee text not null references public.communes(code_insee) on update cascade on delete restrict,
    ancien_nom text,
    date_mouvement date,
    type_mouvement text
);

create index if not exists idx_communes_historique_nouveau
    on public.communes_historique (nouveau_code_insee);

alter table public.communes_historique enable row level security;

create policy "communes_historique_read_all"
    on public.communes_historique
    for select
    using (true);
