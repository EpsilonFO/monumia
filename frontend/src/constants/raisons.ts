import i18n from '@/i18n';
import type { ProjectQuestionnaireAnswers } from '@/types';
import { FAMILLES_KEY } from './familles';

/**
 * Finalités d'une aide (colonne `aides_v3.raison`, constante `RAISONS` côté
 * backend). L'étape « Votre projet » du wizard en fait choisir UNE, et le moteur
 * écarte les aides dont la finalité ne recoupe pas l'intention déclarée : sans
 * ça, un propriétaire qui refait sa façade se voit demander à quelle fréquence
 * sa manifestation est organisée.
 */
export type Raison =
  | 'restauration_travaux'
  | 'valorisation_rayonnement'
  | 'etude_ingenierie'
  | 'fiscalite';

/**
 * Les quatre finalités du catalogue, LIBELLÉS COMPRIS. Sert à relire ce qui est
 * déjà en base (le titre d'un projet sans travaux) — ce que l'étape propose,
 * c'est `RAISON_CHOIX`, qui est plus court.
 */
export const RAISON_OPTIONS: { value: Raison; label: string; hint: string }[] = [
  {
    value: 'restauration_travaux',
    get label() { return i18n.t('constants:raisons.restauration_travaux.label'); },
    get hint() { return i18n.t('constants:raisons.restauration_travaux.hint'); },
  },
  {
    value: 'valorisation_rayonnement',
    get label() { return i18n.t('constants:raisons.valorisation_rayonnement.label'); },
    get hint() { return i18n.t('constants:raisons.valorisation_rayonnement.hint'); },
  },
  {
    value: 'etude_ingenierie',
    get label() { return i18n.t('constants:raisons.etude_ingenierie.label'); },
    get hint() { return i18n.t('constants:raisons.etude_ingenierie.hint'); },
  },
  {
    value: 'fiscalite',
    get label() { return i18n.t('constants:raisons.fiscalite.label'); },
    get hint() { return i18n.t('constants:raisons.fiscalite.hint'); },
  },
];

/**
 * Finalités PROPOSÉES par l'étape « Votre projet ». « Optimiser la fiscalité »
 * n'en est plus : aucune aide du catalogue ne lui est exclusive — Malraux,
 * Denormandie et le label de la Fondation du patrimoine portent tous
 * `restauration_travaux` en plus —, si bien que la choisir ne débloquait rien
 * et, depuis le passage au choix exclusif, faisait perdre les quarante et
 * quelques aides de travaux. Le volet fiscal arrive avec « Restaurer ou faire
 * des travaux ». Retirée de l'écran seulement : la valeur reste dans `Raison`,
 * les projets créés avant gardent leur intention et leur titre.
 */
export const RAISON_CHOIX = RAISON_OPTIONS.filter((o) => o.value !== 'fiscalite');

/** Vrai si l'intention est encore proposée par l'étape « Votre projet ». */
export function raisonProposee(raison: string): boolean {
  return RAISON_CHOIX.some((o) => o.value === raison);
}

/**
 * Clé RÉSERVÉE portant les intentions dans `monument.questionnaire`. Le préfixe
 * « _ » la distingue des réponses aux faits : aucune clé de l'ontologie ne
 * commence par un tiret bas, et le backend isole ces clés avant d'évaluer.
 */
export const RAISONS_KEY = '_raisons';

/**
 * Intentions d'un questionnaire persisté. La liste reste le format stocké —
 * l'étape n'en pose plus qu'une, mais les projets d'avant le passage au choix
 * exclusif en portent plusieurs, et le moteur les accepte toutes.
 */
export function readRaisons(answers: ProjectQuestionnaireAnswers | undefined): string[] {
  const raw = answers?.[RAISONS_KEY];
  return Array.isArray(raw) ? raw.filter((r): r is string => typeof r === 'string') : [];
}

/**
 * Les seules RÉPONSES AUX FAITS d'un questionnaire persisté, sans les clés
 * réservées (`_raisons` aujourd'hui). Pendant de `readRaisons` : à elles deux
 * elles décomposent un `questionnaire` enregistré en ses deux natures.
 *
 * Le questionnaire est reconstitué à l'enregistrement (`{...answers, _raisons}`) :
 * garder les réservées dans l'état des réponses les ferait compter comme des
 * questions à afficher, et les dupliquerait à l'écriture.
 *
 * Même convention de préfixe que `split_reserved_answers` côté backend.
 */
export function sansClesReservees(
  answers: ProjectQuestionnaireAnswers | undefined,
): ProjectQuestionnaireAnswers {
  return Object.fromEntries(
    Object.entries(answers ?? {}).filter(([cle]) => !cle.startsWith('_')),
  );
}

/**
 * « Faire vivre et ouvrir le lieu » n'est pas un chantier : demander « sur
 * quoi portent les travaux ? » juste après contredit ce qu'on vient de cocher.
 * Le wizard saute alors l'étape des travaux et cadre le projet sur « Pas encore
 * déterminé » (`[]`), que le moteur traite en fail-open : les aides à
 * `hard_filters.travaux` restent candidates, comme aujourd'hui pour ce choix.
 *
 * Seule la finalité seule compte : un projet d'avant le choix exclusif, qui
 * porte plusieurs intentions dont un chantier, garde l'étape.
 */
export function sansEtapeTravaux(raisons: string[]): boolean {
  return raisons.length === 1 && raisons[0] === 'valorisation_rayonnement';
}

/**
 * Questionnaire à ENREGISTRER quand le cadrage d'un projet est arrêté (fin de
 * l'étape des travaux, création du projet comprise) : les intentions posées
 * par-dessus les réponses aux faits déjà enregistrées.
 *
 * La finalité est ce qui écarte les aides d'un autre métier (`hors_projet`
 * côté serveur), et elle ne vaut que si elle est PERSISTÉE : la page du projet,
 * le dashboard et l'échéancier relancent le moteur depuis `projet.questionnaire`,
 * sans rien savoir de l'état du wizard. Écrite seulement à la sortie du
 * questionnaire, un projet quitté en cours de route restait sans finalité — sa
 * page listait alors des aides étrangères à ce qu'on venait de cocher.
 *
 * Les réponses aux faits sont RECOPIÉES et non effacées : à ce stade le
 * questionnaire n'a pas été repassé, et « tout refaire » ne les remplace qu'à
 * sa sortie. Les clés réservées du précédent, elles, tombent — `raisons` et
 * `familles` sont les seules sources du cadrage.
 *
 * `familles` est en TRI-ÉTAT (cf. `readFamilles`) : `null` veut dire « la
 * question n'a pas été posée », et la clé est alors ABSENTE du questionnaire —
 * ce qui n'est pas la même chose qu'une liste vide, qui est la réponse
 * « montrez-moi tout ». Les deux ne filtrent rien, mais seule la seconde est un
 * choix, et l'écrire permet de ne pas reposer la question.
 */
export function questionnaireDeCadrage(
  precedent: ProjectQuestionnaireAnswers | undefined,
  raisons: string[],
  familles: string[] | null,
): ProjectQuestionnaireAnswers {
  return {
    ...sansClesReservees(precedent),
    [RAISONS_KEY]: raisons,
    ...(familles === null ? {} : { [FAMILLES_KEY]: familles }),
  };
}
