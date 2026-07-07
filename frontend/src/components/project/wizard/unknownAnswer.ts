import type { QcmOption } from '@/types';

/** Minuscules sans diacritiques, pour matcher « Pas sûr » avec 'pas sur'. */
function normalize(s: string): string {
  return s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '');
}

const UNKNOWN_IDS = new Set(['skip', 'unknown', 'nsp']);

const UNKNOWN_WORDS = [
  'ne sais pas',
  'ne sait pas',
  'je ne sais',
  'incertain',
  'pas sur',
  'aucune idee',
];

/**
 * Détecte les options « Je ne sais pas » du moteur (par id, puis par
 * libellé). Ces options portent un « ? » au lieu d'une pastille lettrée :
 * ce n'est pas une réponse comme les autres. Ne jette jamais.
 */
export function isUnknownAnswer(option: QcmOption): boolean {
  if (UNKNOWN_IDS.has((option.id ?? '').toLowerCase())) return true;
  const label = normalize(option.label ?? '');
  return UNKNOWN_WORDS.some((w) => label.includes(w));
}
