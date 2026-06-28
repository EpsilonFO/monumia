-- Corbeille des documents : un document retiré de TOUS ses projets ET dossiers
-- (ou supprimé par son auteur) est « jeté » sans perte, et récupérable.
-- trashed_at IS NOT NULL  ⟹  monument_ids = '{}' ET dossiers_utilises = '{}'
-- (un document en corbeille est détaché de tout ; appliqué côté code).
-- Pas de backfill : les documents existants restent trashed_at = NULL (non supprimés).
alter table public.documents
  add column if not exists trashed_at timestamptz;
