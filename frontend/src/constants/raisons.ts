import type { ProjectQuestionnaireAnswers } from '@/types';

/**
 * Finalités d'une aide (colonne `aides_v3.raison`, constante `RAISONS` côté
 * backend). L'étape « Votre projet » du wizard les fait cocher, et le moteur
 * écarte les aides dont aucune finalité ne recoupe l'intention déclarée : sans
 * ça, un propriétaire qui refait sa façade se voit demander à quelle fréquence
 * sa manifestation est organisée.
 */
export type Raison =
  | 'restauration_travaux'
  | 'valorisation_rayonnement'
  | 'etude_ingenierie'
  | 'fiscalite';

export const RAISON_OPTIONS: { value: Raison; label: string; hint: string }[] = [
  {
    value: 'restauration_travaux',
    label: 'Restaurer ou faire des travaux',
    hint: 'Toiture, façade, structure, intérieur, mise aux normes.',
  },
  {
    value: 'valorisation_rayonnement',
    label: 'Faire vivre et ouvrir le lieu',
    hint: 'Visites, évènements, activité culturelle ou touristique.',
  },
  {
    value: 'etude_ingenierie',
    label: 'Préparer le projet',
    hint: 'Études, diagnostics, maîtrise d’œuvre en amont du chantier.',
  },
  {
    value: 'fiscalite',
    label: 'Optimiser la fiscalité',
    hint: 'Déductions, exonérations, dispositifs fiscaux du patrimoine.',
  },
];

/**
 * Clé RÉSERVÉE portant les intentions dans `monument.questionnaire`. Le préfixe
 * « _ » la distingue des réponses aux faits : aucune clé de l'ontologie ne
 * commence par un tiret bas, et le backend isole ces clés avant d'évaluer.
 */
export const RAISONS_KEY = '_raisons';

/** Intentions d'un questionnaire persisté. Tolérant aux réponses d'avant l'étape. */
export function readRaisons(answers: ProjectQuestionnaireAnswers | undefined): string[] {
  const raw = answers?.[RAISONS_KEY];
  return Array.isArray(raw) ? raw.filter((r): r is string => typeof r === 'string') : [];
}
