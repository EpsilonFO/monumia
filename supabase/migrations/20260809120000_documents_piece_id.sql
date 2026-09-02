-- Quelle pièce canonique ce document incarne (data/pieces.yaml).
-- Volontairement SANS contrainte de clé étrangère : le référentiel vit dans
-- git, pas en base — même parti pris que les slugs d'aides. La validation se
-- fait au chargement des YAML (pieces_schema) et à l'estampillage.
--
-- Rempli implicitement : quand un document est rattaché à une pièce de
-- checklist qui porte un pieceId, le document est estampillé. Pas de backfill
-- possible (l'information n'existe nulle part avant), les documents existants
-- restent à NULL et se rattacheront au fil des dépôts.
alter table public.documents
  add column if not exists piece_id text;

-- Le stock d'un utilisateur se lit « mes documents portant cette pièce » :
-- l'index sert ce filtre, très sélectif.
create index if not exists idx_documents_piece_id
  on public.documents (piece_id)
  where piece_id is not null;
