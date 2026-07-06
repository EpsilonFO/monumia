/**
 * Répartition des cartes d'aides dans une grille sans case vide.
 *
 * La grille conteneur est `grid-cols-1 sm:grid-cols-2 lg:grid-cols-6` : en lg,
 * une carte sur 2 colonnes donne une rangée de trois, sur 3 colonnes une rangée
 * de deux. On choisit les spans pour que chaque rangée soit pleine quel que
 * soit le nombre de cartes : 2 → duo · 3 → trio · 4 → deux duos · 5 → trio +
 * duo · 6 → deux trios · 7 → trio + deux duos…
 */
export function aideGridSpans(count: number): string[] {
  // n % 3 == 2 → la dernière rangée passe en duo (2 cartes larges).
  // n % 3 == 1 → un seul reliquat ferait une carte orpheline : on convertit
  // les 4 dernières cartes en deux duos.
  const rem = count % 3;
  const wideFrom = rem === 0 ? count : rem === 2 ? count - 2 : count - 4;
  return Array.from({ length: count }, (_, i) => {
    const lg = i >= wideFrom ? 'lg:col-span-3' : 'lg:col-span-2';
    // En sm (2 colonnes), un nombre impair laisserait la dernière carte seule :
    // elle prend alors toute la largeur.
    const sm = count % 2 === 1 && i === count - 1 ? 'sm:col-span-2' : 'sm:col-span-1';
    return `${sm} ${lg}`;
  });
}
