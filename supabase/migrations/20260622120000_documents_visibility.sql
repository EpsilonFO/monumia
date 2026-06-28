-- Droits de consultation par document (projets partagés).
-- visibility :
--   'team'         → tous les membres du projet (défaut, = comportement historique)
--   'responsables' → chef de projet + adjoints (owner/co_owner)
--   'custom'       → uniquement les user_id listés dans allowed_user_ids (+ le chef, toujours)
-- Le chef de projet (owner) et l'auteur voient toujours le document (appliqué en code).
alter table public.documents
  add column if not exists visibility text not null default 'team'
    check (visibility in ('team', 'responsables', 'custom'));

alter table public.documents
  add column if not exists allowed_user_ids uuid[] not null default '{}';
