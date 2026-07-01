/**
 * Suivi de lecture du blog — fonctions pures (aucune dépendance DOM), afin de
 * rester testables en environnement `node`. Le hook `useReadArticles` les
 * branche sur `window.localStorage`.
 */
export const READ_KEY = 'monumia:blog:read';

/** Parse tolérant : toute entrée invalide → ensemble vide (le blog reste navigable). */
export function parseReadSlugs(raw: string | null): Set<string> {
  if (!raw) return new Set();
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((v): v is string => typeof v === 'string'));
  } catch {
    return new Set();
  }
}

export function serializeReadSlugs(slugs: Set<string>): string {
  return JSON.stringify([...slugs]);
}

/** Retourne un NOUVEL ensemble incluant `slug` (immuable). */
export function withRead(slugs: Set<string>, slug: string): Set<string> {
  const next = new Set(slugs);
  next.add(slug);
  return next;
}

export function countRead(readSlugs: Set<string>, slugs: string[]): number {
  return slugs.reduce((n, s) => (readSlugs.has(s) ? n + 1 : n), 0);
}
