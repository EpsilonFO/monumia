import i18n from '@/i18n';
import { PROJECT_STAGES, type ProjectStage, type ProjectStageKey } from '@/lib/project-stats';

/**
 * Ce qu'on fait à chaque étape, pour la ligne « Étape 2 sur 3 : monter le
 * dossier ». L'étape atteinte la plus avancée est celle EN COURS : un projet
 * qui a son diagnostic est « en estimation » tant qu'aucun dossier n'est ouvert.
 */
const ACTION: Record<ProjectStageKey, string> = {
  get estimation() { return i18n.t('libAides:avancement.action.estimation'); },
  get dossier() { return i18n.t('libAides:avancement.action.dossier'); },
  get depot() { return i18n.t('libAides:avancement.action.depot'); },
};

/** Rang (0..2) de l'étape en cours : la plus avancée atteinte, l'estimation si rien. */
export function rangEnCours(stage: ProjectStage): number {
  return Math.max(stage.reachedIndex, 0);
}

export function libelleEtape(stage: ProjectStage): { rang: string; action: string } {
  const i = rangEnCours(stage);
  return {
    rang: i18n.t('libAides:avancement.rang', { rang: i + 1, total: PROJECT_STAGES.length }),
    action: ACTION[PROJECT_STAGES[i].key],
  };
}
