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
