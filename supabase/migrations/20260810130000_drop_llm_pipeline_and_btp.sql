-- Suppression du périmètre mort : pipeline de diagnostic LLM (legacy) et
-- segment « professionnels BTP ».
--
-- Côté LLM : le produit n'appelle plus que le moteur déterministe
-- (eligibility_engine.py, YAML de backend/data/aides/). Ce moteur ne persiste
-- rien et n'utilise pas le pré-filtre SQL — la table `diagnostics` et la
-- fonction `prefiltrer_aides` n'ont plus aucun appelant.
--
-- Côté BTP : le segment n'était plus proposé à l'inscription, l'API /prospects
-- n'était appelée par aucun client, et l'espace /btp est supprimé du frontend.
--
-- ATTENTION : destructif. Les diagnostics historiques et les prospects sont
-- perdus. `aides_v3` n'est PAS touchée — elle sert encore le catalogue lu à la
-- création de dossier et la fiche d'une aide.

-- ── 1. Pipeline LLM ─────────────────────────────────────────────────────────

-- Le trigger lock_owner et les policies RLS tombent avec la table. Pas de
-- CASCADE : une dépendance inattendue doit faire échouer la migration, pas
-- disparaître en silence.
drop table if exists public.diagnostics;

-- Pré-filtre SQL des aides : remplacé par les hard_filters du moteur
-- déterministe, évalués en Python sur les YAML. La signature a changé deux fois
-- (retrait de p_segment, puis passage aux colonnes tableau) : on drope toutes
-- les surcharges plutôt que de parier sur l'état de la base.
do $$
declare
  sig text;
begin
  for sig in
    select p.oid::regprocedure::text
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.proname = 'prefiltrer_aides'
  loop
    execute format('drop function %s', sig);
  end loop;
end
$$;

-- ── 2. Segment BTP : table prospects ────────────────────────────────────────

drop table if exists public.prospects;

-- Ne servait qu'au trigger lock_owner de `prospects`. À ne pas confondre avec
-- public.prevent_owner_change(), qui protège dossiers / documents / monuments /
-- notifications et reste en service.
drop function if exists public.prevent_btp_owner_change();

drop type if exists public.prospect_status;
drop type if exists public.prospect_priorite;

-- ── 3. Segment BTP : profil utilisateur ─────────────────────────────────────

alter table public.users drop column if exists btp;

-- Resserrement de l'enum. Le cast ci-dessous échouerait sur une ligne encore
-- en 'btp' : on requalifie d'abord en 'prive'. Attendu no-op — le garde-fou est
-- là pour que la migration ne bloque pas un déploiement.
do $$
declare
  n integer;
begin
  -- Comparaison en texte : après le resserrement, 'btp' n'est plus une valeur
  -- valide de l'enum et un `segment = 'btp'` échouerait au parse.
  update public.users set segment = 'prive' where segment::text = 'btp';
  get diagnostics n = row_count;
  if n > 0 then
    raise notice '% compte(s) de segment btp requalifié(s) en prive', n;
  end if;
end
$$;

alter type public.user_segment rename to user_segment_old;

create type public.user_segment as enum ('commune', 'prive');

alter table public.users
  alter column segment type public.user_segment
  using segment::text::public.user_segment;

drop type public.user_segment_old;

-- ALTER COLUMN TYPE réécrit la colonne : on rejoue les révocations de
-- 20260506120000_security_hardening.sql pour qu'une éventuelle remise à zéro des
-- droits colonne ne rouvre pas l'auto-élévation de segment.
revoke update (has_aides_access, segment, email) on public.users from authenticated;
revoke update (has_aides_access, segment, email) on public.users from anon;
