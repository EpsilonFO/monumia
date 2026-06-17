import type { ID } from './common.types';

/**
 * Modèle de document fourni par Monumia (bibliothèque centrale).
 * Un modèle est un fichier téléchargeable que l'utilisateur remplit puis
 * ré-uploade comme document de dossier.
 */
export interface Template {
  id: ID;
  slug: string;
  nom: string;
  description?: string;
  /** Clé indicative du type de pièce, ex. "plan_financement". */
  typeDocument: string;
  /** Mots-clés — servent au rapprochement avec les pièces et à la recherche. */
  tags: string[];
  /** Catégories d'aide concernées (ex. "etat_drac") ; vide = générique. */
  categoriesAide: string[];
  organisme?: string;
  /** Chemin du fichier dans le bucket Storage public `templates`. */
  fichierUrl: string;
  nomFichier: string;
  /** Extension (pdf, docx, xlsx, md…) — pilote le badge de format. */
  extension?: string;
  mimeType?: string;
  tailleFichier?: number;
  sourceUrl?: string;
  createdAt?: string;
  updatedAt?: string;
}
