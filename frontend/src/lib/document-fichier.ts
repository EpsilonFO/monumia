import { formatFileSize } from '@/lib/format-utils';
import { getFileExtension } from '@/constants/file-types';

/** Libellé de format de la vignette : l'extension, en capitales (PDF, JPG…). */
export function formatFichier(nomFichier: string): string {
  return getFileExtension(nomFichier).toUpperCase().slice(0, 4) || 'DOC';
}

/** Taille à la française (« 140,6 Ko »). */
export function tailleFichier(octets: number): string {
  return formatFileSize(octets).replace('.', ',');
}
