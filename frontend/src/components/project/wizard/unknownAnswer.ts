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
  'passer cette question',
  'pas encore decide',
];

/**
 * Détecte les réponses « on ne sait pas » : d'abord le drapeau `unknown` du
 * moteur (options `unknown: true` de l'ontologie, pseudo-option « passer »),
 * puis l'id, puis le libellé — les questions du chemin LLM n'ont ni drapeau ni
 * id normalisés. Ces options portent un « ? » au lieu d'une pastille lettrée :
 * ce n'est pas une réponse comme les autres. Ne jette jamais.
 */
export function isUnknownAnswer(option: QcmOption): boolean {
  if (option.unknown) return true;
  if (UNKNOWN_IDS.has((option.id ?? '').toLowerCase())) return true;
  const label = normalize(option.label ?? '');
  return UNKNOWN_WORDS.some((w) => label.includes(w));
}
