import type { QcmQuestion } from '@/types';

/** Drop questions that are missing the array fields we iterate on. Old diagnostics
 *  persisted before validation was tightened can have undefined aideIds. */
export function sanitizeQcmQuestions(questions: QcmQuestion[] | undefined): QcmQuestion[] {
  if (!Array.isArray(questions)) return [];
  return questions.filter(
    (q) => q && Array.isArray(q.aideIds) && q.aideIds.length > 0 && Array.isArray(q.options),
  );
}

/** Compute eliminated aide IDs purely from answers + questions (no API call needed).
 *  Supports both fine-grained (eliminationsParOption) and coarse (eliminatingOptionIds) formats.
 */
export function computeEliminatedAideIds(
  answers: Record<string, string>,
  questions: QcmQuestion[],
): string[] {
  const eliminated = new Set<string>();
  for (const q of questions) {
    const selected = answers[q.id];
    if (!selected || selected === 'skip') continue;
    // Fine-grained: per-option elimination map
    const perOption = q.eliminationsParOption?.[selected];
    if (perOption && perOption.length > 0) {
      for (const aideId of perOption) eliminated.add(aideId);
      continue;
    }
    // Coarse: if selected option is in eliminatingOptionIds, eliminate all aides of the question
    if ((q.eliminatingOptionIds ?? []).includes(selected)) {
      for (const aideId of q.aideIds ?? []) eliminated.add(aideId);
    }
  }
  return [...eliminated];
}
