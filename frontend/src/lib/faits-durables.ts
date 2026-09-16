import type { ProjectQuestionnaireAnswers } from '@/types';

/**
 * Fusion des réponses REPRISES d'un autre projet avec celles de CE projet.
 *
 * Une seule règle, et c'est toute la fonction : **ce qui a été répondu ici
 * gagne**. Les faits durables décrivent le bien et le propriétaire, mais un
 * utilisateur qui a corrigé une réponse sur ce chantier-ci ne doit pas la voir
 * remplacée par celle d'un projet plus ancien — la reprise est une commodité,
 * pas une autorité.
 *
 * Extraite du wizard parce que c'est la seule règle du lot qui se trompe
 * silencieusement : inverser les deux termes du spread ne casse aucun écran,
 * il écrase juste des réponses sans le dire.
 */
export function fusionnerFaitsDurables(
  durables: ProjectQuestionnaireAnswers,
  propres: ProjectQuestionnaireAnswers,
): ProjectQuestionnaireAnswers {
  return { ...durables, ...propres };
}

/**
 * Les faits que la reprise APPORTE réellement — ceux que ce projet ne portait
 * pas déjà. C'est cette liste que le bandeau du questionnaire nomme.
 *
 * Ce n'est pas `Object.keys(durables)` : une réponse durable déjà présente sur
 * ce projet n'a rien été reprise, et l'annoncer ferait dire au bandeau
 * « 12 réponses reprises » là où l'utilisateur n'en reconnaît que trois.
 */
export function clesApportees(
  durables: ProjectQuestionnaireAnswers,
  propres: ProjectQuestionnaireAnswers,
): string[] {
  return Object.keys(durables).filter((cle) => propres[cle] === undefined);
}
