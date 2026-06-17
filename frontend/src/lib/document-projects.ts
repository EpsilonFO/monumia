import type { Document, Monument } from '@/types';

/**
 * Projects the given document can still be copied into: monuments owned by the
 * user, excluding the ones the document is already attached to.
 */
export function availableProjectsForDocument(
  monuments: Monument[],
  userId: string,
  document: Document | null,
): Monument[] {
  if (!document) return [];
  const already = new Set(document.monumentIds);
  return monuments.filter((m) => m.userId === userId && !already.has(m.id));
}
