import type { ID } from './common.types';

export type DocumentType =
  | 'photo' | 'plan' | 'devis' | 'facture' | 'attestation'
  | 'extrait_cadastral' | 'cerfa' | 'arrete' | 'diagnostic'
  | 'rapport' | 'correspondance' | 'autre';

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
  /** Posé quand le document a été retiré de tous ses projets/dossiers (corbeille). */
  trashedAt?: string;
}
