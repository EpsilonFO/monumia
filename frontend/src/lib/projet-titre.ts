import { WORK_TYPES } from '@/constants/monument-options';
import { RAISON_OPTIONS, readRaisons } from '@/constants/raisons';
import type { Projet } from '@/types';

const WORK_LABELS = Object.fromEntries(WORK_TYPES.map((w) => [w.value, w.label]));
const RAISON_LABELS = Object.fromEntries(RAISON_OPTIONS.map((r) => [r.value, r.label]));

/**
 * Titre affiché d'un projet de travaux. Fonction pure.
 *
 * Le champ `titre` est nullable en base — on ne force personne à nommer son
 * chantier avant de savoir ce qu'il contient. À défaut, on le décrit par ce
 * qu'il vise : ses travaux d'abord (c'est ce qui distingue deux projets d'un
 * même monument), ses intentions sinon. Jamais de chaîne vide : la carte et le
 * fil d'Ariane ont toujours quelque chose à afficher.
 */
export function projetTitre(projet: Projet): string {
  if (projet.titre?.trim()) return projet.titre.trim();

  const travaux = projet.travauxEnvisages ?? [];
  if (travaux.length > 0) {
    const noms = travaux.slice(0, 3).map((t) => WORK_LABELS[t] ?? t);
    const reste = travaux.length - noms.length;
    return reste > 0 ? `${noms.join(', ')} +${reste}` : noms.join(', ');
  }

  const raisons = readRaisons(projet.questionnaire);
  if (raisons.length > 0) return RAISON_LABELS[raisons[0]] ?? 'Projet de travaux';

  return 'Projet de travaux';
}
