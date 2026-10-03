/**
 * Les étapes du wizard d'un projet, telles que la colonne gauche les affiche.
 * Rangées à part de `WizardRail` pour que ce fichier-là n'exporte que des
 * composants (rafraîchissement à chaud).
 */

/** Clé d'étape : une chaîne, pas un rang. Le wizard projet en insère selon le
 *  parcours (péril à rattraper, activités, reprise, compte). */
export type WizardStepKey = string;

export interface WizardStep {
  key: WizardStepKey;
  label: string;
  /** La ligne sous l'étape tant qu'elle n'est pas faite. */
  hint: string;
}

/** Étape optionnelle en tête du wizard projet : le monument a été créé avant
 *  que la question du péril n'existe, elle n'a donc jamais été posée. Sans ce
 *  rattrapage, elle ne le serait plus jamais. */
export const PERIL_RATTRAPAGE_STEP: WizardStep = {
  key: 'peril',
  label: 'État du monument',
  hint: 'Une question restée sans réponse sur votre fiche.',
};

/** Étape propre à l'intention « Faire vivre et ouvrir le lieu » : quelles
 *  activités, sur les familles du catalogue. Insérée après l'intention, et
 *  seulement pour elle : « Restaurer » et « Préparer le projet » impliquent
 *  déjà leurs familles côté moteur et n'ont rien à demander. */
export const FAMILLES_STEP: WizardStep = {
  key: 'familles',
  label: 'Les activités',
  hint: 'Ce que vous voulez faire vivre : les aides ne financent pas les mêmes.',
};

/** Étape posée quand le monument porte DÉJÀ un projet : ses réponses durables
 *  (le bien, le propriétaire) peuvent être reprises, et l'utilisateur doit le
 *  dire lui-même. Les reprendre en silence laisserait des réponses décidées
 *  dans son dos, qu'aucune fiche d'aide ne lui offrirait à la correction. */
export const REPRISES_STEP: WizardStep = {
  key: 'reprises',
  label: 'Vos réponses',
  hint: 'Ce que nous savons déjà de votre monument.',
};

export const INTENTION_STEP: WizardStep = {
  key: 'intention',
  label: 'Votre projet',
  hint: 'Ce que vous voulez faire : les aides suivent votre intention.',
};

export const TRAVAUX_STEP: WizardStep = {
  key: 'travaux',
  label: 'Les travaux',
  hint: 'Sur quoi porte le chantier : certaines aides ne financent qu’un ouvrage.',
};

/** Création d'un projet de travaux sur un monument déjà décrit. */
export const PROJET_WIZARD_STEPS: WizardStep[] = [
  INTENTION_STEP,
  TRAVAUX_STEP,
  {
    key: 'questionnaire',
    label: 'Questionnaire',
    hint: 'Quelques minutes, sans aucun document.',
  },
  {
    key: 'diagnostic',
    label: 'Diagnostic',
    hint: 'Les aides mobilisables pour votre projet.',
  },
];

/** Étape de COMPTE, propre au parcours découverte : le diagnostic est calculé,
 *  il ne manque qu'un compte pour l'ouvrir. Elle est dans la colonne dès le
 *  début pour que le visiteur sache où le parcours le mène : la découvrir au
 *  dernier écran se lirait comme un péage surprise.
 *
 *  « Votre compte » plutôt que « Créer mon compte » : l'écran mène à la page de
 *  connexion, qui sert aussi bien à se connecter qu'à s'inscrire. */
export const INSCRIPTION_STEP: WizardStep = {
  key: 'inscription',
  label: 'Votre compte',
  hint: 'Gratuit : votre diagnostic vous attend juste derrière.',
};

/**
 * Parcours DÉCOUVERTE : mêmes étapes qu'un projet ordinaire, plus
 * l'inscription juste avant le diagnostic. La colonne travaille par RANG et
 * non par clé : insérer une étape suffit.
 *
 * L'étape « péril » n'y figure pas, et n'a pas à y figurer : `MonumentForm`
 * impose `etatConservation`, donc un brouillon découverte porte toujours la
 * réponse. Le rattrapage ne concerne que les fiches créées avant la question.
 */
export const PROJET_WIZARD_STEPS_INVITE: WizardStep[] = [
  ...PROJET_WIZARD_STEPS.slice(0, 3),
  INSCRIPTION_STEP,
  ...PROJET_WIZARD_STEPS.slice(3),
];
