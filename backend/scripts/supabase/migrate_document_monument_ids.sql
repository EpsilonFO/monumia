-- Migration: monument_id (single FK) → monument_ids (array of IDs)
-- Allows a document to be linked to multiple monuments.

-- 1. Add the new column
ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS monument_ids text[] DEFAULT '{}';

-- 2. Migrate existing data
UPDATE documents
SET monument_ids = ARRAY[monument_id]
WHERE monument_id IS NOT NULL;

-- 3. Drop old column
ALTER TABLE documents
  DROP COLUMN IF EXISTS monument_id;
