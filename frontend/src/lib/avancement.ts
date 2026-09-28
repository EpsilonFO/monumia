import { PROJECT_STAGES, type ProjectStage, type ProjectStageKey } from '@/lib/project-stats';

/**
 * Ce qu'on fait à chaque étape, pour la ligne « Étape 2 sur 4 : monter le
 * dossier ». L'étape atteinte la plus avancée est celle EN COURS : un projet
 * qui a son diagnostic est « en estimation » tant qu'aucun dossier n'est ouvert.
 */
const ACTION: Record<ProjectStageKey, string> = {
  estimation: 'estimation',
  dossier: 'monter le dossier',
  depot: 'déposer le dossier',
  suivi: 'suivre la réponse',
};

/** Rang (0..3) de l'étape en cours : la plus avancée atteinte, l'estimation si rien. */
export function rangEnCours(stage: ProjectStage): number {
  return Math.max(stage.reachedIndex, 0);
}

export function libelleEtape(stage: ProjectStage): { rang: string; action: string } {
  const i = rangEnCours(stage);
  return { rang: `Étape ${i + 1} sur ${PROJECT_STAGES.length}`, action: ACTION[PROJECT_STAGES[i].key] };
}
