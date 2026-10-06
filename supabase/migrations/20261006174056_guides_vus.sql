-- Visites guidées déjà vues, par compte (2026-10-06).
--
-- Une visite par écran (`monuments`, `monument`, `questionnaire`, `projet`,
-- `aide`, `dossier`), jouée à la première arrivée. La clé est l'identifiant de
-- la visite, la valeur la date où elle a été vue ou passée. Écrite par
-- `PATCH /auth/me/guides`, remise à zéro par `DELETE /auth/me/guides` (bouton
-- « Revoir les visites guidées » du profil). Le patron est celui de
-- `notification_preferences` : un jsonb sur `users`, lu avec le profil.

alter table public.users
  add column if not exists guides_vus jsonb not null default '{}'::jsonb;

-- Épargner les comptes existants : décommenter pour qu'ils ne voient aucune
-- visite (ils connaissent déjà l'application). Laissé commenté par défaut :
-- les écrans ont changé depuis, la visite leur sert aussi.
--
-- update public.users
--    set guides_vus = jsonb_build_object(
--      'monuments', now(), 'monument', now(), 'questionnaire', now(),
--      'projet', now(), 'aide', now(), 'dossier', now()
--    )
--  where created_at < now();
