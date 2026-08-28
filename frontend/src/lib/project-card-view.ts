import type { MonumentStats, ProjectStats } from '@/lib/project-stats';

export type JalonState = 'done' | 'current' | 'upcoming';

/** État d'un jalon du parcours selon l'index de la dernière étape atteinte. */
export function jalonState(index: number, reachedIndex: number): JalonState {
  if (index < reachedIndex) return 'done';
  if (index === reachedIndex) return 'current';
  return 'upcoming';
}

export type MontantTileMode = 'money' | 'count' | 'nudge';

/**
 * Mode d'affichage de la tuile motivation :
 *  - 'money' : un montant potentiel > 0 est connu ;
 *  - 'count' : pas de montant chiffré mais au moins une aide identifiée ;
 *  - 'nudge' : aucune estimation exploitable (pas de stats ou 0 aide).
 *
 * Accepte indifféremment les chiffres d'un projet ou l'agrégat d'un monument :
 * la tuile pose la même question aux deux grains.
 */
export function montantTileMode(
  stats?: Pick<ProjectStats | MonumentStats, 'aidesIdentifiees' | 'montantPotentiel'>
): MontantTileMode {
  if (!stats || stats.aidesIdentifiees === 0) return 'nudge';
  if (stats.montantPotentiel > 0) return 'money';
  return 'count';
}
