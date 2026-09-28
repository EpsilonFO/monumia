import type { ID } from './common.types';

/**
 * Miroir de l'enum `document_type` de la base et de `TYPE_DOCUMENTS`
 * (backend/pieces_schema.py). Les six derniers viennent de la migration
 * 20260928143556. Libellés, familles et icônes : lib/document-type-meta.ts.
 */
export type DocumentType =
  | 'photo' | 'plan' | 'devis' | 'facture' | 'attestation'
  | 'extrait_cadastral' | 'cerfa' | 'arrete' | 'diagnostic'
  | 'rapport' | 'correspondance' | 'autre'
  | 'autorisation_urbanisme' | 'rib' | 'titre_propriete'
  | 'deliberation' | 'statuts' | 'plan_financement';

export type DocumentVisibility = 'team' | 'responsables' | 'custom';

export interface Document {
  id: ID;
  /** Monuments auxquels la pièce est rattachée (arrêté, cadastre, photos…). */
  monumentIds: ID[];
  /** Projets de travaux auxquels elle est rattachée : ne la voient qu'eux. */
  projetIds: ID[];
  userId: ID;

  nom: string;
  nomFichier: string;
  type: DocumentType;
  tags: string[];

  tailleFichier: number;
  mimeType: string;
  url: string;

  dossiersUtilises: ID[];

  dateUpload: string;
  dateDocument?: string;
  description?: string;
  visibility: DocumentVisibility;
  allowedUserIds: ID[];
  /**
   * La pièce du référentiel (backend/data/pieces.yaml) que ce fichier incarne :
   * posée au dépôt depuis « À déposer pour vos aides », ou quand il est joint à
   * une pièce de dossier. C'est elle qui le fait reprendre ailleurs.
   */
  pieceId?: string;
  /** Posé quand le document a été retiré de tous ses projets/dossiers (corbeille). */
  trashedAt?: string;
}
