-- Migration : remplacer les colonnes JSONB "commune" et "prive" par des colonnes scalaires
-- À exécuter dans Supabase SQL Editor

BEGIN;

-- =============================================
-- COMMUNE : JSONB → FK + colonne fonction
-- =============================================

-- 1. Ajouter les nouvelles colonnes
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS commune_code_insee TEXT,
  ADD COLUMN IF NOT EXISTS commune_fonction   TEXT;

-- 2. Migrer les données existantes depuis le JSONB
UPDATE users
SET
  commune_code_insee = commune ->> 'codeInsee',
  commune_fonction   = commune ->> 'fonction'
WHERE commune IS NOT NULL
  AND commune ->> 'codeInsee' IS NOT NULL;

-- 3. Ajouter la contrainte FK
ALTER TABLE users
  ADD CONSTRAINT fk_users_commune
  FOREIGN KEY (commune_code_insee) REFERENCES communes (code_insee);

-- 4. Supprimer l'ancienne colonne JSONB
ALTER TABLE users DROP COLUMN IF EXISTS commune;

-- =============================================
-- PRIVE : JSONB → 2 colonnes scalaires
-- =============================================

-- 5. Ajouter les nouvelles colonnes
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS prive_type_proprietaire TEXT,
  ADD COLUMN IF NOT EXISTS prive_regime_fiscal     TEXT;

-- 6. Migrer les données existantes depuis le JSONB
UPDATE users
SET
  prive_type_proprietaire = prive ->> 'typeProprietaire',
  prive_regime_fiscal     = prive ->> 'regimeFiscal'
WHERE prive IS NOT NULL;

-- 7. Supprimer l'ancienne colonne JSONB
ALTER TABLE users DROP COLUMN IF EXISTS prive;

COMMIT;
