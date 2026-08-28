-- Suppression du segment utilisateur (commune / privé) et des colonnes de profil
-- qui en dépendaient.
--
-- Pourquoi : le segment ne pilotait aucune décision métier. L'éligibilité se joue
-- entièrement sur `monuments.proprietaire` (10 valeurs, par projet), que le moteur
-- déterministe lit ; `users.segment` n'était relu par aucun router. Les données
-- collectées par segment n'alimentaient rien non plus : `commune_*` n'était
-- qu'affiché en page profil, et `prive_regime_fiscal` employait un vocabulaire
-- distinct du fait `regime_fiscal` de l'ontologie (lui-même utilisé par 0 aide).
--
-- Les critères propres au propriétaire ont désormais un seul foyer : les faits
-- `scope: proprietaire` de backend/data/facts.yaml.
--
-- ATTENTION : destructif. Ces colonnes sont perdues. L'inscription ne demande
-- plus que email, mot de passe, nom, prénom et téléphone (optionnel).

-- La contrainte fk_users_commune (commune_code_insee → communes.code_insee) ne
-- porte que sur cette colonne : PostgreSQL la supprime avec elle, sans CASCADE.
alter table public.users drop column if exists commune_code_insee;
alter table public.users drop column if exists commune_fonction;
alter table public.users drop column if exists prive_type_proprietaire;
alter table public.users drop column if exists prive_regime_fiscal;

-- Retire aussi l'entrée d'ACL colonne posée par 20260506120000_security_hardening.sql
-- (`revoke update (has_aides_access, segment, email)`) : elle disparaît avec la
-- colonne. Les révocations sur has_aides_access et email restent en place.
alter table public.users drop column if exists segment;

drop type if exists public.user_segment;
