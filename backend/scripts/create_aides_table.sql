-- ============================================================================
-- Table: aides
-- Stores all available financial aids for heritage monument restoration.
-- The "criteres" column is JSONB containing eligibility criteria with
-- camelCase keys (matching the frontend Aide type and the matching engine).
-- ============================================================================
DROP TABLE IF EXISTS aides;
CREATE TABLE IF NOT EXISTS aides (
  id             TEXT PRIMARY KEY,
  nom            TEXT NOT NULL,
  nom_court      TEXT NOT NULL,
  description    TEXT NOT NULL,
  description_longue TEXT,
  categorie      TEXT NOT NULL,        -- etat_drac, region, departement, fondation_patrimoine, fiscalite, mecenat, autre
  type           TEXT NOT NULL,        -- subvention, label, souscription, deduction_fiscale, mecenat, autre
  organisme      TEXT NOT NULL,

  montant_max    NUMERIC,
  taux_max       NUMERIC,
  montant_min    NUMERIC,
  plancher       NUMERIC,

  criteres       JSONB NOT NULL DEFAULT '{}',

  demarche_description TEXT,
  documents_requis     JSONB DEFAULT '[]',   -- text[]
  delai_instruction    TEXT,

  date_ouverture  DATE,
  date_limite     DATE,
  permanent       BOOLEAN NOT NULL DEFAULT true,

  url_officielle  TEXT,
  formulaire_url  TEXT,

  tags            JSONB DEFAULT '[]',        -- text[]
  base_ttc        BOOLEAN NOT NULL DEFAULT false,

  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index on categorie for filtered queries
CREATE INDEX IF NOT EXISTS idx_aides_categorie ON aides (categorie);

-- Enable RLS (read-only for all authenticated users)
ALTER TABLE aides ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Aides are readable by all authenticated users"
  ON aides FOR SELECT
  TO authenticated
  USING (true);

-- Only service role can insert/update/delete
-- (no policy needed — service_role bypasses RLS)
