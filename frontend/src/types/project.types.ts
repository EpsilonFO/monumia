/** Réponses au questionnaire projet, indexées par id de question. */
export type ProjectQuestionnaireAnswers = Record<string, string>;

/** Une question du questionnaire projet (placeholder lorem-ipsum, contenu définitif en Phase ultérieure). */
export interface QuestionnaireQuestion {
  id: string;
  question: string;
  options: { id: string; label: string }[];
}

/** Questionnaire placeholder — 3 questions, texte lorem-ipsum, à remplacer par le contenu métier. */
export const QUESTIONNAIRE_QUESTIONS: QuestionnaireQuestion[] = [
  {
    id: 'q1',
    question: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit ?',
    options: [
      { id: 'q1a', label: 'Sed do eiusmod tempor' },
      { id: 'q1b', label: 'Incididunt ut labore' },
      { id: 'q1c', label: 'Et dolore magna aliqua' },
    ],
  },
  {
    id: 'q2',
    question: 'Ut enim ad minim veniam, quis nostrud exercitation ?',
    options: [
      { id: 'q2a', label: 'Ullamco laboris nisi' },
      { id: 'q2b', label: 'Ut aliquip ex ea' },
      { id: 'q2c', label: 'Commodo consequat' },
      { id: 'q2d', label: 'Duis aute irure' },
    ],
  },
  {
    id: 'q3',
    question: 'Excepteur sint occaecat cupidatat non proident ?',
    options: [
      { id: 'q3a', label: 'Sunt in culpa qui' },
      { id: 'q3b', label: 'Officia deserunt mollit' },
      { id: 'q3c', label: 'Anim id est laborum' },
    ],
  },
];
