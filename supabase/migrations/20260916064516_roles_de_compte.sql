-- `administrateurs` devient `comptes_roles` : la même table, une colonne de
-- plus, et un second rôle.
--
-- Deux rôles de COMPTE, à ne pas confondre avec les rôles d'ÉQUIPE
-- (`project_members.role`, `projet_members.role` : co_owner / member), qui
-- portent sur un monument ou un chantier et ne se gèrent pas ici :
--
--   * `admin`        — la page /admin : retirer une aide, reformuler une
--                      question, modifier un critère, nommer les rôles ;
--   * `beta_testeur` — aucun droit d'administration, mais l'offre
--                      Multi-monuments sans facturation, le temps des tests.
--
-- Les deux ouvrent la même offre aujourd'hui, pour deux raisons différentes :
-- l'administrateur parce qu'il doit pouvoir regarder le catalogue depuis le
-- produit, le bêta-testeur parce qu'on lui demande de l'essayer en entier.
-- C'est `services/roles.py` qui en décide (`ROLES_AVEC_OFFRE`), pas la base.
--
-- Une migration séparée plutôt qu'une réécriture de `20260916062229` : cette
-- dernière a pu être appliquée entre-temps. Les deux s'enchaînent sur une base
-- neuve et donnent le même état.

alter table public.administrateurs rename to comptes_roles;

-- `default 'admin'` le temps de la migration : les lignes existantes sont des
-- administrateurs, par construction. Le défaut est retiré juste après — un rôle
-- doit être choisi explicitement à l'insertion.
alter table public.comptes_roles add column role text not null default 'admin';
alter table public.comptes_roles alter column role drop default;

-- Un compte peut cumuler les deux rôles : la clé devient composite.
alter table public.comptes_roles drop constraint administrateurs_pkey;
alter table public.comptes_roles add primary key (user_id, role);

-- Le lot des rôles connus est fermé côté base aussi : une valeur inventée
-- n'ouvrirait rien côté applicatif, mais elle traînerait dans la table sans que
-- personne la voie passer.
alter table public.comptes_roles
    add constraint comptes_roles_role_connu check (role in ('admin', 'beta_testeur'));

-- Les contraintes ne suivent pas le renommage de la table : on les renomme pour
-- qu'un message d'erreur de Postgres continue de désigner la bonne table.
alter table public.comptes_roles
    rename constraint administrateurs_user_id_fkey to comptes_roles_user_id_fkey;
alter table public.comptes_roles
    rename constraint administrateurs_ajoute_par_fkey to comptes_roles_ajoute_par_fkey;

-- RLS et grants suivent la table, mais on les réaffirme : seul le service-role
-- du backend lit et écrit ici, derrière `require_admin`.
alter table public.comptes_roles enable row level security;
revoke all on public.comptes_roles from anon, authenticated;
