/**
 * Réponses au questionnaire projet, indexées par clé de fait (`fact_key`) du
 * moteur d'aides → id de l'option choisie. Le questionnaire lui-même n'est plus
 * statique : ses questions sont générées par le diagnostic déterministe
 * (faits manquants), cf. `QcmQuestion` dans `aide.types.ts`.
 *
 * Les clés préfixées « _ » sont RÉSERVÉES : elles ne désignent pas un fait mais
 * une métadonnée du diagnostic, transportée dans le même dict parce qu'il est
 * persisté tel quel dans `monument.questionnaire` et retransmis à chaque appel.
 * Aujourd'hui : `_raisons` (string[]), les intentions de l'étape « Votre projet »
 * (cf. `constants/raisons.ts`). Le backend les isole avant d'évaluer les faits
 * (`split_reserved_answers`).
 */
export type ProjectQuestionnaireAnswers = Record<string, string | string[]>;
