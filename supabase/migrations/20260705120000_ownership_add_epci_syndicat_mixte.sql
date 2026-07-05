-- Ajoute deux types de propriétaire à l'ontologie d'ownership :
--   public_epci     — Intercommunalité (EPCI)
--   syndicat_mixte  — Syndicat mixte / Parc naturel régional
--
-- Motivation : de nombreuses aides régionales (ex. Région Bretagne) rendent
-- éligibles les EPCI et les syndicats mixtes / PNR, non représentables jusqu'ici
-- par l'enum ownership_type (monuments.proprietaire) ni par ref_proprietaires.
-- Faute de ces codes, l'éligibilité de ces porteurs restait en manual_check.
--
-- ALTER TYPE ... ADD VALUE est additif et irréversible (pas de DROP VALUE en
-- PostgreSQL) ; IF NOT EXISTS rend la migration idempotente.

ALTER TYPE public.ownership_type ADD VALUE IF NOT EXISTS 'public_epci' AFTER 'public_commune';
ALTER TYPE public.ownership_type ADD VALUE IF NOT EXISTS 'syndicat_mixte' AFTER 'public_etat';

-- Table de référence (code -> libellé) alignée sur backend/labels.py.
INSERT INTO public.ref_proprietaires (code, label) VALUES
  ('public_epci', 'Intercommunalité (EPCI)'),
  ('syndicat_mixte', 'Syndicat mixte / Parc naturel régional')
ON CONFLICT (code) DO UPDATE SET label = EXCLUDED.label;
