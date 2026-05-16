ALTER TABLE public.monuments
DROP COLUMN IF EXISTS affectataire,
DROP COLUMN IF EXISTS periode_construction,
DROP COLUMN IF EXISTS superficie,
DROP COLUMN IF EXISTS materiaux,
DROP COLUMN IF EXISTS type_couverture,
DROP COLUMN IF EXISTS nombre_niveaux,
DROP COLUMN IF EXISTS urgence_travaux,
DROP COLUMN IF EXISTS diagnostic_realise,
DROP COLUMN IF EXISTS derniers_travaux,
DROP COLUMN IF EXISTS description_etat;