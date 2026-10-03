import { libelleFamille } from '@/constants/familles';
import type { AideMatchResult } from '@/types';

/**
 * Facettes de FAMILLE sur la liste d'aides d'un projet — le mode découverte.
 *
 * Pendant d'`aide-filtres` (le financeur), sur l'autre axe : le THÈME. Les deux
 * se cumulent, et pour une raison de fond — « je ne sais pas encore, montrez-moi
 * tout » est la moitié annoncée des usages de « faire vivre le lieu », et
 * quelqu'un qui n'a rien voulu cocher au cadrage a besoin de trier ENSUITE, sur
 * la liste qu'il a sous les yeux.
 *
 * Contrairement aux filtres de financeur, la liste des facettes n'est pas fermée
 * à l'avance : elle est l'UNION des familles portées par les aides du projet.
 * Une facette qui ne laisserait rien n'existe donc jamais.
 */
export interface FamilleFacette {
  famille: string;
  label: string;
  count: number;
}

/** Vrai si l'aide relève de cette famille. `null` (aucune facette choisie)
 *  accepte tout, y compris les aides sans famille. */
export function matchFamille(match: AideMatchResult, famille: string | null): boolean {
  if (famille === null) return true;
  return (match.aide.familles ?? []).includes(famille);
}

export function filtrerParFamille(
  aides: AideMatchResult[],
  famille: string | null,
): AideMatchResult[] {
  if (famille === null) return aides;
  return aides.filter((m) => matchFamille(m, famille));
}

/**
 * Les facettes à afficher, comptées sur les aides passées.
 *
 * Triées par compte décroissant puis par libellé : à l'inverse de la barre de
 * financeur, dont l'ordre est fixe, ces puces n'ont pas d'ordre naturel — la
 * plus fournie en tête est alors le seul rangement qui aide.
 *
 * Une seule facette ne départage rien : la barre disparaît. La facette
 * SÉLECTIONNÉE est conservée même vide, sinon la puce qu'on vient de choisir
 * s'évanouirait sous les doigts.
 *
 * Les aides sans famille ne sont comptées nulle part et restent visibles tant
 * qu'aucune facette n'est choisie : le fail-open du cadrage, à l'écran.
 */
export function famillesDisponibles(
  aides: AideMatchResult[],
  selection: string | null,
): FamilleFacette[] {
  const comptes = new Map<string, number>();
  for (const m of aides) {
    for (const famille of m.aide.familles ?? []) {
      comptes.set(famille, (comptes.get(famille) ?? 0) + 1);
    }
  }
  if (selection !== null && !comptes.has(selection)) comptes.set(selection, 0);
  const facettes = [...comptes.entries()]
    .map(([famille, count]) => ({ famille, label: libelleFamille(famille), count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, 'fr'));
  return facettes.length > 1 ? facettes : [];
}
