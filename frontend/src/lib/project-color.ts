// Palette de couleurs distinctes et lisibles sur fond crème, pour identifier
// visuellement chaque projet. La couleur n'est JAMAIS la seule information :
// le nom du projet est toujours affiché à côté (public non-technique, accessibilité).
export const PROJECT_PALETTE = [
  'var(--cat-1)',  'var(--cat-2)',  'var(--cat-3)',  'var(--cat-4)',  'var(--cat-5)',
  'var(--cat-6)',  'var(--cat-7)',  'var(--cat-8)',  'var(--cat-9)',  'var(--cat-10)',
] as const;

// Teinte douce assortie à chaque couleur de projet (même ordre que PROJECT_PALETTE),
// pour laver le fond d'une carte dans la couleur du projet sans nuire à la lisibilité.
export const PROJECT_PALETTE_SOFT = [
  'var(--cat-1-soft)',  'var(--cat-2-soft)',  'var(--cat-3-soft)',  'var(--cat-4-soft)',  'var(--cat-5-soft)',
  'var(--cat-6-soft)',  'var(--cat-7-soft)',  'var(--cat-8-soft)',  'var(--cat-9-soft)',  'var(--cat-10-soft)',
] as const;

/** Index de couleur stable d'un projet, dérivé de son id (hash simple, déterministe). */
export function projectColorIndex(id: string): number {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  }
  return hash % PROJECT_PALETTE.length;
}

/** Couleur pleine stable d'un projet (bandeau, chiffre, frise). */
export function projectColor(id: string): string {
  return PROJECT_PALETTE[projectColorIndex(id)];
}

/** Teinte douce assortie (fond lavé de carte), du même projet. */
export function projectColorSoft(id: string): string {
  return PROJECT_PALETTE_SOFT[projectColorIndex(id)];
}
