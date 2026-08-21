-- Durcissement RLS après audit du 2026-08-19.
--
-- Contexte : les 23 tables de `public` ont bien RLS activé et l'isolation entre
-- comptes est correcte (testée avec deux comptes réels : lecture, écriture,
-- suppression croisées, usurpation de user_id, contournement par or=(),
-- traversée par jointures imbriquées, Storage). Les trous ne venaient pas de
-- l'isolation mais du périmètre des policies et de grants inutilisés.
--
-- Constat qui justifie l'ampleur des REVOKE ci-dessous : le front n'appelle
-- jamais PostgREST pour les tables. `getSupabase()` ne sert qu'à l'auth et au
-- Storage (frontend/src/services/document.service.ts:59), aucun `.from()`
-- n'existe côté client, aucune publication realtime n'est configurée, et tout
-- l'accès aux données passe par le backend via le client service-role
-- (backend/db.py:41), qui contourne RLS de toute façon. Les privilèges DML
-- accordés à anon/authenticated sur `public` ne servent donc à rien.


-- ---------------------------------------------------------------------------
-- 1. P0 + P1 : `users` — cloisonner les colonnes, pas seulement la ligne
-- ---------------------------------------------------------------------------
-- La policy « users: update own » délimite la ligne (auth.uid() = id) mais pas
-- les colonnes. Deux conséquences vérifiées :
--
--   * has_aides_access est auto-attribuable. Un simple
--     PATCH /rest/v1/users?id=eq.<soi> {"has_aides_access": true}
--     renvoyait 200 et débloquait tout le produit payant, via
--     _has_manual_grant -> _user_has_all_access -> has_monument_access, après
--     quoi redact_diagnostic_if_locked ne caviarde plus rien.
--
--   * stripe_customer_id est réinscriptible. POST /billing/portal ouvre un
--     portail Stripe pour l'id client lu dans la ligne de l'appelant
--     (routers/billing.py:186), et _user_id_for_customer résout l'utilisateur
--     par cette colonne en maybe_single() (routers/billing.py:245).
--
-- La policy reste correcte : c'est le grant qui doit être restreint aux
-- colonnes réellement éditables par leur propriétaire. Tout le reste
-- (has_aides_access, stripe_customer_id, email, id, created_at…) devient
-- écrivable seulement par le service-role, donc par le backend.
REVOKE UPDATE, INSERT, DELETE, TRUNCATE, REFERENCES, TRIGGER
  ON public.users FROM anon, authenticated;

GRANT UPDATE (prenom, nom, telephone, onboarding_complete,
              notification_preferences, metier)
  ON public.users TO authenticated;


-- ---------------------------------------------------------------------------
-- 2. P2 : retirer les `SELECT USING (true)` sur les tables du paywall
-- ---------------------------------------------------------------------------
-- Ces quatre policies rendaient le catalogue payant lisible par tout compte
-- inscrit, abonné ou non, en contournant redact_diagnostic_if_locked. Aucun
-- appelant légitime : le front ne lit jamais ces tables et le backend passe
-- par le service-role.
DROP POLICY IF EXISTS aides_v3_read        ON public.aides_v3;
DROP POLICY IF EXISTS aide_conditions_read ON public.aide_conditions;
DROP POLICY IF EXISTS facts_read           ON public.facts;
DROP POLICY IF EXISTS templates_read       ON public.templates;

REVOKE ALL ON public.aides_v3, public.aide_conditions,
              public.facts, public.templates
  FROM anon, authenticated;


-- ---------------------------------------------------------------------------
-- 3. P3 : couper les privilèges d'écriture inutilisés
-- ---------------------------------------------------------------------------
-- Douze tables portaient l'empreinte d'un GRANT ALL (DELETE, INSERT,
-- REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE) pour anon ET authenticated.
-- Seules les policies RLS retenaient la clé anon, et TRUNCATE n'est JAMAIS
-- filtré par RLS : un jour où une fonction SECURITY DEFINER ou un accès SQL
-- direct existerait, la clé anon pourrait vider ces tables.
--
-- anon n'a aucune raison d'écrire quoi que ce soit : toutes les policies
-- d'écriture reposent sur auth.uid(), qui est NULL pour anon (vérifié : les
-- INSERT anon renvoyaient déjà 42501). On retire donc l'écriture entièrement.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
  ON ALL TABLES IN SCHEMA public FROM anon;

-- authenticated garde le DML dont ses policies ont besoin, mais TRUNCATE,
-- TRIGGER et REFERENCES ne servent à aucun cas d'usage produit.
REVOKE TRUNCATE, TRIGGER, REFERENCES
  ON ALL TABLES IN SCHEMA public FROM authenticated;

-- Et on empêche les futures tables de repartir avec un GRANT ALL implicite.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  REVOKE TRUNCATE, TRIGGER, REFERENCES ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  REVOKE INSERT, UPDATE, DELETE ON TABLES FROM anon;


-- ---------------------------------------------------------------------------
-- 4. P3 : code mort exposé à anon, au-dessus d'une table sans RLS
-- ---------------------------------------------------------------------------
-- public.match_document_chunks() était exécutable par anon et lisait
-- `document_chunks` sans le moindre filtre de propriété. Non exploitable en
-- l'état (anon n'a ni USAGE sur le schéma vecs ni SELECT sur la table, vecs
-- n'est pas exposé à PostgREST, et la fonction est cassée : ses colonnes
-- chunk_id/document_id/filename/content/embedding ne correspondent pas aux
-- colonnes réelles id/vec/metadata, d'où un 42P01 à l'appel). Mais c'est le
-- gabarit exact d'une fuite totale dès que quelqu'un « réparerait » la
-- fonction ou ouvrirait le schéma.
DROP FUNCTION IF EXISTS public.match_document_chunks(vector, integer);

-- Ceinture et bretelles sur la table de contenus documentaires, qui était la
-- seule du projet à n'avoir aucune protection RLS. Sans policy, RLS bloque
-- tout sauf le service-role : c'est exactement l'état voulu ici.
ALTER TABLE IF EXISTS vecs.document_chunks ENABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------------
-- Optionnel : rattacher les policies au rôle `authenticated`
-- ---------------------------------------------------------------------------
-- Cinq tables (monuments, documents, dossiers, notifications, users) ont des
-- policies liées au rôle `public`, qui englobe anon. Elles échouent bien en
-- pratique, car auth.uid() est NULL pour anon et NULL = user_id ne vaut jamais
-- true. La section 3 rend le sujet inoffensif pour l'écriture en retirant le
-- DML à anon. Reste la lecture, elle aussi fermée par le même NULL.
--
-- Je laisse donc ce nettoyage commenté : il est purement cosmétique après la
-- section 3, et un DROP/CREATE de policy sur les tables chaudes mérite d'être
-- joué séparément, pas glissé dans une migration de durcissement.
--
--   DROP POLICY "monuments: select own" ON public.monuments;
--   CREATE POLICY "monuments: select own" ON public.monuments
--     FOR SELECT TO authenticated USING (auth.uid() = user_id);
--   -- idem pour les policies INSERT/DELETE de monuments, documents,
--   -- dossiers, notifications, et la policy SELECT de users.


-- ---------------------------------------------------------------------------
-- Hors périmètre SQL : à corriger dans le code
-- ---------------------------------------------------------------------------
-- GET /aides/{aide_id} (backend/routers/aides.py:150) n'a aucune dépendance
-- d'authentification et n'appelle jamais redact_locked_aide. Il rend la fiche
-- complète d'une aide sans compte, par UUID comme par slug, et les slugs sont
-- les 141 noms de fichiers de backend/data/aides/, donc le catalogue entier est
-- énumérable. Aucune policy RLS ne peut rattraper ça : la route passe par le
-- client service-role. Le correctif est un Depends(get_current_user_id) plus
-- un passage par le filtre de paywall, dans le routeur.
