-- ============================================================================
-- AIDES V2 — Normalised schema for pre-filtering + LLM matching
--
-- Strategy:
--   1. Simple filterable criteria → dedicated join tables (SQL WHERE/JOIN)
--   2. Scalar criteria → columns on aides
--   3. Complex/nuanced conditions → free-text field for LLM evaluation
--
-- Run this migration in Supabase SQL Editor.
-- ============================================================================

-- =========================
-- 1. Reference enum tables
-- =========================

-- Niveaux de protection MH
CREATE TABLE IF NOT EXISTS ref_protections (
  code TEXT PRIMARY KEY,          -- classe, inscrit, abords, spr, non_protege
  label TEXT NOT NULL
);
INSERT INTO ref_protections (code, label) VALUES
  ('classe',      'Classé Monument Historique'),
  ('inscrit',     'Inscrit Monument Historique'),
  ('abords',      'Périmètre abords MH'),
  ('spr',         'Site Patrimonial Remarquable'),
  ('non_protege', 'Non protégé')
ON CONFLICT (code) DO NOTHING;

-- Types de propriétaire
CREATE TABLE IF NOT EXISTS ref_proprietaires (
  code TEXT PRIMARY KEY,
  label TEXT NOT NULL
);
INSERT INTO ref_proprietaires (code, label) VALUES
  ('public_commune',           'Commune'),
  ('public_departement',       'Département'),
  ('public_region',            'Région'),
  ('public_etat',              'État'),
  ('prive_personne_physique',  'Personne physique'),
  ('prive_sci',                'SCI'),
  ('association',              'Association'),
  ('mixte',                    'Propriété mixte')
ON CONFLICT (code) DO NOTHING;

-- Types de travaux
CREATE TABLE IF NOT EXISTS ref_travaux (
  code TEXT PRIMARY KEY,
  label TEXT NOT NULL
);
INSERT INTO ref_travaux (code, label) VALUES
  ('toiture',              'Toiture'),
  ('charpente',            'Charpente'),
  ('couverture',           'Couverture'),
  ('facade',               'Façade'),
  ('maconnerie',           'Maçonnerie'),
  ('vitraux',              'Vitraux'),
  ('peintures_murales',    'Peintures murales'),
  ('menuiserie',           'Menuiserie'),
  ('electricite',          'Électricité'),
  ('plomberie',            'Plomberie'),
  ('chauffage',            'Chauffage'),
  ('accessibilite',        'Accessibilité'),
  ('mise_en_securite',     'Mise en sécurité'),
  ('restauration_generale','Restauration générale'),
  ('etude_prealable',      'Étude préalable'),
  ('mobilier',             'Mobilier'),
  ('orgues',               'Orgues'),
  ('parcs_jardins',        'Parcs et jardins'),
  ('protection_solaire',   'Protection solaire'),
  ('ventilation',          'Ventilation')
ON CONFLICT (code) DO NOTHING;

-- Segments utilisateur
CREATE TABLE IF NOT EXISTS ref_segments (
  code TEXT PRIMARY KEY,
  label TEXT NOT NULL
);
INSERT INTO ref_segments (code, label) VALUES
  ('commune', 'Commune'),
  ('prive',   'Propriétaire privé'),
  ('btp',     'Entreprise BTP')
ON CONFLICT (code) DO NOTHING;

-- États de conservation
CREATE TABLE IF NOT EXISTS ref_etats_conservation (
  code TEXT PRIMARY KEY,
  label TEXT NOT NULL
);
INSERT INTO ref_etats_conservation (code, label) VALUES
  ('bon',     'Bon état'),
  ('moyen',   'État moyen'),
  ('mauvais', 'Mauvais état'),
  ('peril',   'En péril')
ON CONFLICT (code) DO NOTHING;


-- =========================
-- 2. Table aides (v2)
-- =========================

-- Drop old table (CAREFUL: only if you're OK losing existing data —
-- in production, use ALTER TABLE + data migration instead)
-- DROP TABLE IF EXISTS aides CASCADE;

CREATE TABLE IF NOT EXISTS aides_v2 (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nom               TEXT NOT NULL,
  nom_court         TEXT NOT NULL,
  description       TEXT NOT NULL,
  description_longue TEXT,

  categorie         TEXT NOT NULL,    -- etat_drac, region, departement, fondation, fiscalite, mecenat, europe
  type              TEXT NOT NULL,    -- subvention, deduction_fiscale, exoneration, pret, mecenat, appel_a_projets, label, souscription
  organisme         TEXT NOT NULL,

  -- Financier
  montant_max       NUMERIC,
  taux_max          NUMERIC,
  montant_min       NUMERIC,
  plancher          NUMERIC,
  base_ttc          BOOLEAN NOT NULL DEFAULT false,

  -- Critères scalaires (pré-filtrage simple)
  commune_max_population  INTEGER,         -- NULL = pas de contrainte
  cofinancement_requis    BOOLEAN NOT NULL DEFAULT false,
  architecte_requis       BOOLEAN NOT NULL DEFAULT false,

  -- Texte libre pour conditions complexes (matching LLM)
  conditions_eligibilite_detail TEXT,      -- Texte brut copié/résumé des sources officielles

  -- Démarche
  demarche_description   TEXT,
  documents_requis       JSONB DEFAULT '[]',
  delai_instruction      TEXT,

  -- Calendrier
  date_ouverture   DATE,
  date_limite      DATE,
  permanent        BOOLEAN NOT NULL DEFAULT true,

  -- Liens
  url_officielle   TEXT,
  formulaire_url   TEXT,

  -- Métadonnées
  tags             JSONB DEFAULT '[]',
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- =========================
-- 3. Tables de jointure (critères multi-valués)
-- =========================

-- Protections requises par aide
CREATE TABLE IF NOT EXISTS aides_protections (
  aide_id        UUID NOT NULL REFERENCES aides_v2(id) ON DELETE CASCADE,
  protection_code TEXT NOT NULL REFERENCES ref_protections(code),
  PRIMARY KEY (aide_id, protection_code)
);

-- Propriétaires éligibles par aide
CREATE TABLE IF NOT EXISTS aides_proprietaires (
  aide_id           UUID NOT NULL REFERENCES aides_v2(id) ON DELETE CASCADE,
  proprietaire_code TEXT NOT NULL REFERENCES ref_proprietaires(code),
  PRIMARY KEY (aide_id, proprietaire_code)
);

-- Travaux éligibles par aide
CREATE TABLE IF NOT EXISTS aides_travaux (
  aide_id      UUID NOT NULL REFERENCES aides_v2(id) ON DELETE CASCADE,
  travaux_code TEXT NOT NULL REFERENCES ref_travaux(code),
  PRIMARY KEY (aide_id, travaux_code)
);

-- Régions éligibles par aide (NULL = toute la France)
CREATE TABLE IF NOT EXISTS aides_regions (
  aide_id     UUID NOT NULL REFERENCES aides_v2(id) ON DELETE CASCADE,
  region_code TEXT NOT NULL,   -- slug : bretagne, ile-de-france, etc. FK vers communes.region possible
  PRIMARY KEY (aide_id, region_code)
);

-- Départements éligibles par aide (NULL = tous)
CREATE TABLE IF NOT EXISTS aides_departements (
  aide_id          UUID NOT NULL REFERENCES aides_v2(id) ON DELETE CASCADE,
  departement_code TEXT NOT NULL,   -- code INSEE : 01, 2A, 974, etc.
  PRIMARY KEY (aide_id, departement_code)
);

-- Segments éligibles par aide (NULL = tous)
CREATE TABLE IF NOT EXISTS aides_segments (
  aide_id      UUID NOT NULL REFERENCES aides_v2(id) ON DELETE CASCADE,
  segment_code TEXT NOT NULL REFERENCES ref_segments(code),
  PRIMARY KEY (aide_id, segment_code)
);

-- États de conservation requis par aide (NULL = tous)
CREATE TABLE IF NOT EXISTS aides_etats_conservation (
  aide_id              UUID NOT NULL REFERENCES aides_v2(id) ON DELETE CASCADE,
  etat_conservation_code TEXT NOT NULL REFERENCES ref_etats_conservation(code),
  PRIMARY KEY (aide_id, etat_conservation_code)
);


-- =========================
-- 4. Index pour le pré-filtrage
-- =========================

CREATE INDEX IF NOT EXISTS idx_aides_v2_categorie ON aides_v2 (categorie);
CREATE INDEX IF NOT EXISTS idx_aides_v2_permanent ON aides_v2 (permanent);
CREATE INDEX IF NOT EXISTS idx_aides_v2_commune_pop ON aides_v2 (commune_max_population);

CREATE INDEX IF NOT EXISTS idx_aides_protections_code ON aides_protections (protection_code);
CREATE INDEX IF NOT EXISTS idx_aides_proprietaires_code ON aides_proprietaires (proprietaire_code);
CREATE INDEX IF NOT EXISTS idx_aides_travaux_code ON aides_travaux (travaux_code);
CREATE INDEX IF NOT EXISTS idx_aides_regions_code ON aides_regions (region_code);
CREATE INDEX IF NOT EXISTS idx_aides_departements_code ON aides_departements (departement_code);
CREATE INDEX IF NOT EXISTS idx_aides_segments_code ON aides_segments (segment_code);
CREATE INDEX IF NOT EXISTS idx_aides_etats_code ON aides_etats_conservation (etat_conservation_code);


-- =========================
-- 5. RLS
-- =========================

-- Aides : lecture seule pour tous les utilisateurs authentifiés
ALTER TABLE aides_v2 ENABLE ROW LEVEL SECURITY;
CREATE POLICY "aides_v2_read" ON aides_v2 FOR SELECT TO authenticated USING (true);

-- Tables de jointure : même politique
ALTER TABLE aides_protections ENABLE ROW LEVEL SECURITY;
CREATE POLICY "aides_protections_read" ON aides_protections FOR SELECT TO authenticated USING (true);

ALTER TABLE aides_proprietaires ENABLE ROW LEVEL SECURITY;
CREATE POLICY "aides_proprietaires_read" ON aides_proprietaires FOR SELECT TO authenticated USING (true);

ALTER TABLE aides_travaux ENABLE ROW LEVEL SECURITY;
CREATE POLICY "aides_travaux_read" ON aides_travaux FOR SELECT TO authenticated USING (true);

ALTER TABLE aides_regions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "aides_regions_read" ON aides_regions FOR SELECT TO authenticated USING (true);

ALTER TABLE aides_departements ENABLE ROW LEVEL SECURITY;
CREATE POLICY "aides_departements_read" ON aides_departements FOR SELECT TO authenticated USING (true);

ALTER TABLE aides_segments ENABLE ROW LEVEL SECURITY;
CREATE POLICY "aides_segments_read" ON aides_segments FOR SELECT TO authenticated USING (true);

ALTER TABLE aides_etats_conservation ENABLE ROW LEVEL SECURITY;
CREATE POLICY "aides_etats_conservation_read" ON aides_etats_conservation FOR SELECT TO authenticated USING (true);

-- Ref tables : lecture pour tous
ALTER TABLE ref_protections ENABLE ROW LEVEL SECURITY;
CREATE POLICY "ref_protections_read" ON ref_protections FOR SELECT TO authenticated USING (true);

ALTER TABLE ref_proprietaires ENABLE ROW LEVEL SECURITY;
CREATE POLICY "ref_proprietaires_read" ON ref_proprietaires FOR SELECT TO authenticated USING (true);

ALTER TABLE ref_travaux ENABLE ROW LEVEL SECURITY;
CREATE POLICY "ref_travaux_read" ON ref_travaux FOR SELECT TO authenticated USING (true);

ALTER TABLE ref_segments ENABLE ROW LEVEL SECURITY;
CREATE POLICY "ref_segments_read" ON ref_segments FOR SELECT TO authenticated USING (true);

ALTER TABLE ref_etats_conservation ENABLE ROW LEVEL SECURITY;
CREATE POLICY "ref_etats_conservation_read" ON ref_etats_conservation FOR SELECT TO authenticated USING (true);


-- =========================
-- 6. Fonction de pré-filtrage SQL
-- =========================
-- Retourne les aides potentiellement éligibles pour un monument donné.
-- Les paramètres NULL sont ignorés (pas de filtre sur ce critère).

CREATE OR REPLACE FUNCTION prefiltrer_aides(
  p_protection       TEXT     DEFAULT NULL,
  p_proprietaire     TEXT     DEFAULT NULL,
  p_travaux          TEXT[]   DEFAULT NULL,
  p_region           TEXT     DEFAULT NULL,
  p_departement      TEXT     DEFAULT NULL,
  p_segment          TEXT     DEFAULT NULL,
  p_population       INTEGER  DEFAULT NULL,
  p_etat_conservation TEXT    DEFAULT NULL
)
RETURNS TABLE (aide_id UUID)
LANGUAGE sql STABLE
AS $$
  SELECT DISTINCT a.id
  FROM aides_v2 a
  WHERE
    -- Protection : l'aide n'a aucune contrainte OU le monument matche
    (NOT EXISTS (SELECT 1 FROM aides_protections ap WHERE ap.aide_id = a.id)
     OR EXISTS (SELECT 1 FROM aides_protections ap WHERE ap.aide_id = a.id AND ap.protection_code = p_protection))

    -- Propriétaire
    AND (NOT EXISTS (SELECT 1 FROM aides_proprietaires ap WHERE ap.aide_id = a.id)
     OR EXISTS (SELECT 1 FROM aides_proprietaires ap WHERE ap.aide_id = a.id AND ap.proprietaire_code = p_proprietaire))

    -- Travaux : au moins un travaux en commun
    AND (NOT EXISTS (SELECT 1 FROM aides_travaux at2 WHERE at2.aide_id = a.id)
     OR EXISTS (SELECT 1 FROM aides_travaux at2 WHERE at2.aide_id = a.id AND at2.travaux_code = ANY(p_travaux)))

    -- Région
    AND (NOT EXISTS (SELECT 1 FROM aides_regions ar WHERE ar.aide_id = a.id)
     OR EXISTS (SELECT 1 FROM aides_regions ar WHERE ar.aide_id = a.id AND ar.region_code = p_region))

    -- Département
    AND (NOT EXISTS (SELECT 1 FROM aides_departements ad WHERE ad.aide_id = a.id)
     OR EXISTS (SELECT 1 FROM aides_departements ad WHERE ad.aide_id = a.id AND ad.departement_code = p_departement))

    -- Segment
    AND (NOT EXISTS (SELECT 1 FROM aides_segments as2 WHERE as2.aide_id = a.id)
     OR EXISTS (SELECT 1 FROM aides_segments as2 WHERE as2.aide_id = a.id AND as2.segment_code = p_segment))

    -- Population
    AND (a.commune_max_population IS NULL OR p_population IS NULL OR p_population <= a.commune_max_population)

    -- État de conservation
    AND (NOT EXISTS (SELECT 1 FROM aides_etats_conservation ae WHERE ae.aide_id = a.id)
     OR EXISTS (SELECT 1 FROM aides_etats_conservation ae WHERE ae.aide_id = a.id AND ae.etat_conservation_code = p_etat_conservation))

    -- Pas expirée
    AND (a.permanent = true OR a.date_limite IS NULL OR a.date_limite >= CURRENT_DATE)
  ;
$$;
