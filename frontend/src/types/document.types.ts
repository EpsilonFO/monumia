import type { ID } from './common.types';

export type DocumentType =
  | 'photo' | 'plan' | 'devis' | 'facture' | 'attestation'
  | 'extrait_cadastral' | 'cerfa' | 'arrete' | 'diagnostic'
  | 'rapport' | 'correspondance' | 'autre';

export interface Document {
  id: ID;
  monumentId?: ID;
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
}
