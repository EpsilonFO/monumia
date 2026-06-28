// Palette de couleurs distinctes et lisibles sur fond crème, pour identifier
// visuellement chaque projet. La couleur n'est JAMAIS la seule information :
// le nom du projet est toujours affiché à côté (public non-technique, accessibilité).
export const PROJECT_PALETTE = [
  '#0a369d', // bleu Monumia
  '#f17105', // orange Monumia
  '#0f766e', // sarcelle
  '#7c3aed', // violet
  '#b91c1c', // rouge brique
  '#0369a1', // bleu ciel profond
  '#a16207', // ocre
  '#9d174d', // framboise
  '#15803d', // vert
  '#4338ca', // indigo
] as const;

/** Couleur stable d'un projet, dérivée de son id (hash simple, déterministe). */
export function projectColor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  }
  return PROJECT_PALETTE[hash % PROJECT_PALETTE.length];
}
