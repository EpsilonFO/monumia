/**
 * Réponses au questionnaire projet, indexées par clé de fait (`fact_key`) du
 * moteur d'aides → id de l'option choisie. Le questionnaire lui-même n'est plus
 * statique : ses questions sont générées par le diagnostic déterministe
 * (faits manquants), cf. `QcmQuestion` dans `aide.types.ts`.
 */
export type ProjectQuestionnaireAnswers = Record<string, string>;
