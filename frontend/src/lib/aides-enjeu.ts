import { formatCurrency, formatPercentage } from '@/lib/format-utils';
import type { ProjectStats } from '@/lib/project-stats';

/**
 * Formulation de l'enjeu chiffré d'un projet, telle qu'elle s'affiche dans la
 * case « Aides mobilisables ».
 *
 * Deux registres, parce que les aides ne se chiffrent pas toutes de la même
 * façon : un montant plafond en euros (somme des `montant_max`) et une part du
 * coût des travaux (taux cumulé, écrêté à 80 % côté moteur — le maître
 * d'ouvrage garde au moins 20 % à sa charge). D'où le « et / ou » : selon
 * l'aide, c'est l'un, l'autre, ou le moindre des deux qui s'applique.
 *
 * « Jusqu'à » et non « montant potentiel » : additionner les plafonds décrit un
 * maximum théorique, pas une prévision — personne ne décroche toutes les aides
 * repérées, et personne ne monte tous les dossiers.
 */
export interface EnjeuLabel {
  /** Ligne principale, jamais vide (« — » quand rien n'est chiffré). */
  value: string;
  /** Seconde ligne, dans la même case : « et / ou 60 % des travaux ». */
  sub?: string;
}

export function enjeuLabel(stats: Pick<ProjectStats, 'montantPotentiel' | 'tauxTravauxMax'>): EnjeuLabel {
  const { montantPotentiel, tauxTravauxMax } = stats;
  const taux = tauxTravauxMax > 0 ? `${formatPercentage(tauxTravauxMax)} des travaux` : null;

  if (montantPotentiel > 0) {
    return { value: `Jusqu’à ${formatCurrency(montantPotentiel)}`, sub: taux ? `et / ou ${taux}` : undefined };
  }
  // Aucune aide plafonnée en euros : le taux porte seul la case.
  if (taux) return { value: `Jusqu’à ${taux}` };
  return { value: '—' };
}
