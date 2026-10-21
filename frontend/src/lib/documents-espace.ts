import { localeIntl } from '@/i18n/format';
import { dossierLabel, typeLabel } from '@/lib/document-type-meta';
import type { Document, DocumentType } from '@/types';

/**
 * L'espace « Mes documents » (maquette `monumia-documents.html`) : recherche,
 * tri, récents, dossiers. Fonctions pures, partagées par la page et par les
 * onglets Documents d'un monument et d'un projet.
 */

export type TriDocuments = 'date' | 'nom';
export type VueDocuments = 'grille' | 'liste';

/** « Récents » : les N derniers ajouts. */
export const NB_RECENTS = 10;

const sansAccents = (s: string) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

/**
 * Recherche dans le nom, le nom de fichier, les étiquettes, et le type sous ses
 * deux libellés (« devis » trouve le dossier Devis, « photos » le type Photo).
 * Insensible à la casse et aux accents.
 */
export function rechercherDocuments(docs: Document[], recherche: string): Document[] {
  const q = sansAccents(recherche.trim());
  if (!q) return docs;
  return docs.filter((d) =>
    [d.nom, d.nomFichier, typeLabel(d.type), dossierLabel(d.type), ...d.tags].some((t) => sansAccents(t).includes(q)),
  );
}

const horodatage = (d: Document) => {
  const t = Date.parse(d.dateUpload);
  return Number.isNaN(t) ? 0 : t;
};

/** « Les plus récents d'abord » (date d'ajout) ou « Trier par nom ». Ne modifie pas la liste reçue. */
export function trierDocuments(docs: Document[], tri: TriDocuments): Document[] {
  const copie = [...docs];
  if (tri === 'nom') return copie.sort((a, b) => a.nom.localeCompare(b.nom, localeIntl(), { sensitivity: 'base' }));
  return copie.sort((a, b) => horodatage(b) - horodatage(a) || a.nom.localeCompare(b.nom, localeIntl()));
}

/** Les derniers ajouts, quel que soit le tri affiché. */
export function documentsRecents(docs: Document[], n = NB_RECENTS): Document[] {
  return trierDocuments(docs, 'date').slice(0, n);
}

/** Nombre de documents par type (les dossiers vides n'ont pas de clé). */
export function compterParType(docs: Document[]): Partial<Record<DocumentType, number>> {
  const n: Partial<Record<DocumentType, number>> = {};
  docs.forEach((d) => { n[d.type] = (n[d.type] ?? 0) + 1; });
  return n;
}

/** Poids total, en octets. */
export function tailleTotale(docs: Document[]): number {
  return docs.reduce((s, d) => s + (d.tailleFichier || 0), 0);
}

/** Le nom proposé pour un fichier déposé : sans extension, tirets et soulignés changés en espaces. */
export function nomDepuisFichier(nomFichier: string): string {
  return nomFichier.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim();
}

const EXT_IMAGES = new Set(['JPG', 'JPEG', 'PNG', 'HEIC', 'HEIF', 'WEBP', 'GIF', 'BMP', 'AVIF', 'SVG']);

/** Pastille de format verte pour une image, bleue sinon (maquette `.ext.img`). */
export function estImage(format: string, mimeType = ''): boolean {
  return mimeType.startsWith('image/') || EXT_IMAGES.has(format.toUpperCase());
}
