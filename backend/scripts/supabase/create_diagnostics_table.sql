-- Table: diagnostics
-- Stores the results of aide diagnostic runs for each monument.
DROP TABLE IF EXISTS diagnostics;
CREATE TABLE IF NOT EXISTS diagnostics (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  monument_id   UUID NOT NULL REFERENCES monuments(id) ON DELETE CASCADE,
  user_id       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  -- Inputs
  mode_projet       BOOLEAN NOT NULL DEFAULT FALSE,
  travaux_filtres    JSONB,            -- list of WorkType strings, nullable

  -- Summary
  total_aides_analysees    INTEGER NOT NULL,
  aides_eligibles_count    INTEGER NOT NULL,
  aides_non_eligibles_count INTEGER NOT NULL,
  montant_potentiel_total  NUMERIC,

  -- Only store aide UUIDs (FK to aides.uuid); criteria are recomputed at read time
  aides_eligibles_ids       UUID[] NOT NULL DEFAULT '{}',
  aides_non_eligibles_ids   UUID[] NOT NULL DEFAULT '{}',

  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index: fast lookup by monument
CREATE INDEX IF NOT EXISTS idx_diagnostics_monument_id ON diagnostics(monument_id);

-- Index: fast lookup by user
CREATE INDEX IF NOT EXISTS idx_diagnostics_user_id ON diagnostics(user_id);

-- RLS policies
ALTER TABLE diagnostics ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read their own diagnostics"
  ON diagnostics FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own diagnostics"
  ON diagnostics FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own diagnostics"
  ON diagnostics FOR DELETE
  USING (auth.uid() = user_id);
