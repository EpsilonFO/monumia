-- Add a free-form JSONB column to persist the project questionnaire answers
-- collected during the unified Projet wizard. Additive and pre-launch: the
-- frontend degrades gracefully (keeps answers in component state) if missing.
ALTER TABLE monuments ADD COLUMN IF NOT EXISTS questionnaire jsonb;
