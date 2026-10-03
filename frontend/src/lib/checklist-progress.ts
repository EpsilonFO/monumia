import type { ChecklistItem, Dossier } from '@/types';

/**
 * Deux chiffres distincts : une pièce « reprise » est rattachée mais pas
 * confirmée, elle ne doit donc jamais gonfler la progression réelle du dossier.
 * Le backend applique la même règle (_recalculate_progression ne compte que
 * les items « fourni »).
 */
export function compterChecklist(items: ChecklistItem[]): {
  confirmees: number;
  aVerifier: number;
  total: number;
} {
  return {
    confirmees: items.filter((i) => i.statut === 'fourni').length,
    aVerifier: items.filter((i) => i.statut === 'repris').length,
    total: items.length,
  };
}

/**
 * L'anneau de la carte d'un dossier : la part des pièces confirmées sur toutes
 * les pièces, le même compte que la page du dossier. Calculé ici plutôt que lu
 * sur `progressionPourcentage`, que le serveur n'écrit qu'au fil des dépôts :
 * un dossier qui n'a pas bougé depuis un changement de règle garderait son
 * ancien chiffre. Un dossier déposé est à 100 %, comme le serveur l'enregistre.
 */
export function progressionDossier(dossier: Pick<Dossier, 'statut' | 'checklist'>): number {
  if (dossier.statut === 'soumis') return 100;
  const { confirmees, total } = compterChecklist(dossier.checklist);
  return total > 0 ? Math.round((confirmees / total) * 100) : 0;
}
