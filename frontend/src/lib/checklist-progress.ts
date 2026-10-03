import type { ChecklistItem } from '@/types';

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
