-- Six types de document en plus des douze d'origine.
--
-- Les aides demandent souvent des pièces que les douze types rangeaient mal :
-- le RIB tombait dans « Attestation », les statuts et le titre de propriété
-- dans « Autre », la délibération et l'autorisation d'urbanisme dans
-- « Arrêté », le plan de financement dans « Rapport ». La page « Mes
-- documents » les range désormais en quatre familles (le monument, les
-- travaux, l'administratif et financier, les échanges), et chaque pièce du
-- référentiel (backend/data/pieces.yaml) a enfin un type qui lui ressemble.
--
-- Miroirs à garder d'accord : `DocumentType` (frontend/src/types/
-- document.types.ts) et `TYPE_DOCUMENTS` (backend/pieces_schema.py).
--
-- `add value` ne peut pas servir dans la transaction qui l'ajoute : ce fichier
-- ne fait donc qu'ajouter les valeurs, sans rien réécrire.

alter type public.document_type add value if not exists 'autorisation_urbanisme';
alter type public.document_type add value if not exists 'rib';
alter type public.document_type add value if not exists 'titre_propriete';
alter type public.document_type add value if not exists 'deliberation';
alter type public.document_type add value if not exists 'statuts';
alter type public.document_type add value if not exists 'plan_financement';
