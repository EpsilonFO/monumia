// Palette de couleurs distinctes et lisibles sur fond crème, pour identifier
// visuellement chaque projet. La couleur n'est JAMAIS la seule information :
// le nom du projet est toujours affiché à côté (public non-technique, accessibilité).
export const PROJECT_PALETTE = [
  'var(--cat-1)',  'var(--cat-2)',  'var(--cat-3)',  'var(--cat-4)',  'var(--cat-5)',
  'var(--cat-6)',  'var(--cat-7)',  'var(--cat-8)',  'var(--cat-9)',  'var(--cat-10)',
] as const;

/** Couleur stable d'un projet, dérivée de son id (hash simple, déterministe). */
export function projectColor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  }
  return PROJECT_PALETTE[hash % PROJECT_PALETTE.length];
}
