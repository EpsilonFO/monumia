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
 * puis l'id, puis le libellé — le repli par libellé couvre les options dont
 * l'ontologie ne normalise ni le drapeau ni l'id. Ces options portent un « ? »
 * au lieu d'une pastille lettrée : ce n'est pas une réponse comme les autres.
 * Ne jette jamais.
 *
 * `unknown: false` EXPLICITE court-circuite le repli par libellé : quand le
 * fait déclare ses réponses, le moteur émet le drapeau dans les deux sens (cf.
 * `build_questions`), et une réponse de plein droit nommée « Je ne sais pas
 * trop » hériterait sinon du « ? », du tri en bas de liste et de l'exclusivité
 * en choix multiple. Le repli ne sert plus qu'aux options FABRIQUÉES par le
 * moteur, qui n'ont rien à déclarer.
 */
export function isUnknownAnswer(option: QcmOption): boolean {
  if (option.unknown) return true;
  if (option.unknown === false) return false;
  if (UNKNOWN_IDS.has((option.id ?? '').toLowerCase())) return true;
  const label = normalize(option.label ?? '');
  return UNKNOWN_WORDS.some((w) => label.includes(w));
}
