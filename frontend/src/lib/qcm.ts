import type { QcmQuestion } from '@/types';

/** Drop questions that are missing the array fields we iterate on. Old diagnostics
 *  persisted before validation was tightened can have undefined aideIds. */
export function sanitizeQcmQuestions(questions: QcmQuestion[] | undefined): QcmQuestion[] {
  if (!Array.isArray(questions)) return [];
  return questions.filter(
    (q) => q && Array.isArray(q.aideIds) && q.aideIds.length > 0 && Array.isArray(q.options),
  );
}

/** Ids « je ne sais pas » d'une question : ils ne portent aucune élimination. */
function isSkipId(q: QcmQuestion, id: string): boolean {
  return id === 'skip' || (q.options.find((o) => o.id === id)?.unknown ?? false);
}

/** Compute eliminated aide IDs purely from answers + questions (no API call needed).
 *  Supports both fine-grained (eliminationsParOption) and coarse (eliminatingOptionIds) formats.
 *
 *  Question à choix multiple : la réponse est un tableau d'ids et une aide n'est
 *  écartée que si CHAQUE case cochée l'écarte — cocher une case de plus ne peut
 *  que libérer des aides (sémantique existentielle du moteur, cf. MultiValue).
 *  Sauf les exclusions strictes (`eliminationsStrictesParOption`) : une seule
 *  case cochée suffit à écarter l'aide.
 */
export function computeEliminatedAideIds(
  answers: Record<string, string | string[]>,
  questions: QcmQuestion[],
): string[] {
  const eliminated = new Set<string>();
  for (const q of questions) {
    const answer = answers[q.id];
    const selected = (Array.isArray(answer) ? answer : [answer]).filter(
      (id): id is string => !!id && !isSkipId(q, id),
    );
    if (selected.length === 0) continue;

    // Exclusions strictes : union sur la sélection.
    for (const id of selected) {
      for (const aideId of q.eliminationsStrictesParOption?.[id] ?? []) eliminated.add(aideId);
    }

    // Fine-grained: per-option elimination map, intersected across the selection.
    let common: string[] | null = null;
    for (const id of selected) {
      const perOption = q.eliminationsParOption?.[id] ?? [];
      common = common === null ? perOption : common.filter((a) => perOption.includes(a));
      if (common.length === 0) break;
    }
    if (common && common.length > 0) {
      for (const aideId of common) eliminated.add(aideId);
      continue;
    }
    // Coarse: eliminate all aides of the question when EVERY selected option does
    const coarse = q.eliminatingOptionIds ?? [];
    if (coarse.length > 0 && selected.every((id) => coarse.includes(id))) {
      for (const aideId of q.aideIds ?? []) eliminated.add(aideId);
    }
  }
  return [...eliminated];
}

/**
 * Ce que la réponse à CETTE question écarte de plus que les autres réponses,
 * et pourquoi : le contenu de l'encart affiché sous les réponses du
 * questionnaire, avant que l'utilisateur ne clique sur « Continuer ».
 *
 * On ne compte que les aides encore en lice : dire « cette réponse écarte
 * 12 aides » quand dix l'étaient déjà par le porteur serait faux, et
 * l'utilisateur chercherait en vain à les récupérer en changeant sa réponse.
 *
 * Le texte vient du fait (`pourquoiEcarte`) : celui de la réponse choisie,
 * sinon le repli `'*'`. En choix multiple, une aide ne tombe que si AUCUNE
 * case cochée ne lui convient, si bien que le texte d'une case ne vaut que si
 * elle est seule cochée ; au-delà, seul le repli dit vrai. `pourquoi` vaut
 * `null` quand le fait n'a rien à dire : l'encart garde alors son compte.
 */
export function ecartParReponse(
  question: QcmQuestion,
  answers: Record<string, string | string[]>,
  questions: QcmQuestion[],
): { nbAides: number; pourquoi: string | null } | null {
  const selection = selectedIds(question, answers).filter((id) => !isSkipId(question, id));
  if (selection.length === 0) return null;
  const autres = { ...answers };
  delete autres[question.id];
  const deja = new Set(computeEliminatedAideIds(autres, questions));
  const nouvelles = computeEliminatedAideIds({ [question.id]: selection }, [question]).filter(
    (id) => !deja.has(id),
  );
  if (nouvelles.length === 0) return null;
  const textes = question.pourquoiEcarte ?? {};
  const propre = selection.length === 1 ? textes[selection[0]] : undefined;
  return { nbAides: nouvelles.length, pourquoi: propre ?? textes['*'] ?? null };
}

/** Une question ne sert plus à rien quand TOUTES les aides qu'elle débloque sont
 *  déjà écartées par les réponses précédentes : la poser ferait perdre du temps
 *  sans rien changer au résultat (« durée d'engagement de location » alors que
 *  le bâtiment n'est pas mis en location).
 *
 *  Fail-open : sans `aideIds` exploitable, on garde la question — mieux vaut une
 *  question de trop qu'une aide écartée sans que l'utilisateur l'ait su.
 */
export function isQuestionServingLiveAide(
  question: QcmQuestion,
  eliminatedAideIds: Iterable<string>,
): boolean {
  const ids = question.aideIds;
  if (!Array.isArray(ids) || ids.length === 0) return true;
  const eliminated = eliminatedAideIds instanceof Set ? eliminatedAideIds : new Set(eliminatedAideIds);
  return ids.some((id) => !eliminated.has(id));
}

/**
 * Réponse à une question, toujours vue comme une liste d'ids : une seule case
 * pour une question simple, plusieurs pour une question à choix multiple.
 */
export function selectedIds(
  question: QcmQuestion,
  answers: Record<string, string | string[]>,
): string[] {
  const answer = answers[question.id];
  if (Array.isArray(answer)) return answer;
  return typeof answer === 'string' ? [answer] : [];
}

/**
 * Une question conditionnelle n'est posée que si la réponse à la question dont
 * elle dépend la rend pertinente. Fail-closed : tant que cette question n'est
 * pas répondue (ou qu'elle est passée), on pose quand même — mieux vaut une
 * question de trop qu'une aide écartée sans que l'utilisateur l'ait su.
 * Le moteur garantit que la question porteuse est posée AVANT ses dépendantes.
 * Sur une question porteuse à choix multiple, une seule case pertinente suffit.
 */
export function isVisible(
  question: QcmQuestion,
  answers: Record<string, string | string[]>,
): boolean {
  const dep = question.dependsOn;
  if (!dep) return true;
  const answer = answers[dep.questionId];
  const given = (Array.isArray(answer) ? answer : [answer]).filter(
    (id): id is string => typeof id === 'string' && id !== 'skip',
  );
  if (given.length === 0) return true;
  return given.some((id) => dep.showForOptionIds.includes(id));
}

/**
 * Seuil du TRONC COMMUN : une question mérite le questionnaire général quand
 * elle départage au moins deux aides encore vivantes. En dessous, elle ne
 * concerne qu'une aide et se pose là où l'utilisateur regarde cette aide —
 * c'est ce qui casse la croissance linéaire du questionnaire (la moitié des
 * faits du catalogue ne sont cités que par une seule aide).
 */
export const MIN_AIDES_TRONC_COMMUN = 2;

/** Nombre d'aides de la question que les réponses précédentes n'ont pas écartées. */
export function countLiveAides(question: QcmQuestion, eliminated: Set<string>): number {
  const ids = question.aideIds;
  if (!Array.isArray(ids)) return 0;
  return ids.reduce((n, id) => (eliminated.has(id) ? n : n + 1), 0);
}

/**
 * La question porte-t-elle sur assez d'aides vivantes pour le tronc commun ?
 *
 * Fail-open comme `isQuestionServingLiveAide` : sans `aideIds` exploitable, on
 * garde la question dans le tronc — mieux vaut une question de trop qu'une
 * question reléguée sur une carte qu'on n'ouvrira jamais.
 */
export function isQuestionPartagee(
  q: QcmQuestion,
  eliminated: Set<string>,
  min = MIN_AIDES_TRONC_COMMUN,
): boolean {
  const ids = q.aideIds;
  if (!Array.isArray(ids) || ids.length === 0) return true;
  return countLiveAides(q, eliminated) >= min;
}

/**
 * Répartit les questions ENCORE UTILES (vivantes et pertinentes au vu des
 * réponses) entre le tronc commun et celles propres à une seule aide.
 *
 * Règle `dependsOn` : LA PORTEUSE SUIT SA DÉPENDANTE DANS LE TRONC. Une
 * question branchée sur une autre n'a de sens que si la porteuse a été posée ;
 * si la dépendante est partagée, sa porteuse reste donc dans le tronc même
 * quand elle ne sert qu'une aide. L'inverse n'est jamais vrai : on n'évince
 * jamais une dépendante partagée à cause de sa porteuse. Le cas `applies_if`
 * est redondant (les aideIds de la dépendante sont inclus dans ceux de la
 * porteuse) ; le cas déduction (`ouverture_public` →
 * `jours_ouverture_public_par_an`), aux aideIds indépendants, ne l'est pas.
 */
export function partitionnerQuestions(
  questions: QcmQuestion[],
  answers: Record<string, string | string[]>,
  min = MIN_AIDES_TRONC_COMMUN,
): { tronc: QcmQuestion[]; propres: QcmQuestion[] } {
  const eliminated = new Set(computeEliminatedAideIds(answers, questions));
  const vivantes = questions.filter(
    (q) => isVisible(q, answers) && isQuestionServingLiveAide(q, eliminated),
  );
  const tronc = new Set(
    vivantes.filter((q) => isQuestionPartagee(q, eliminated, min)).map((q) => q.id),
  );
  // Remontée des porteuses jusqu'au point fixe : le corpus n'a qu'un niveau de
  // branchement, mais une chaîne A → B → C ne coûte que quelques passes et
  // évite de laisser une question orpheline de sa porteuse.
  const parId = new Map(vivantes.map((q) => [q.id, q]));
  for (let passe = 0; passe < vivantes.length; passe++) {
    let change = false;
    for (const q of vivantes) {
      const dep = q.dependsOn;
      if (!dep || !tronc.has(q.id) || tronc.has(dep.questionId)) continue;
      if (parId.has(dep.questionId)) {
        tronc.add(dep.questionId);
        change = true;
      }
    }
    if (!change) break;
  }
  return {
    tronc: vivantes.filter((q) => tronc.has(q.id)),
    propres: vivantes.filter((q) => !tronc.has(q.id)),
  };
}
