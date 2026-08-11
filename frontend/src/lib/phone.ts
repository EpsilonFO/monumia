/**
 * Validation d'un numéro de téléphone français, tolérante sur la mise en forme :
 * indicatif +33 / 0033 / 0, puis un chiffre non nul, puis quatre paires
 * éventuellement séparées par un espace, un point ou un tiret.
 *
 * Le champ étant optionnel partout, la chaîne vide est valide.
 */
const FR_PHONE_REGEX = /^(?:\+33|0033|0)[1-9](?:[\s.-]?\d{2}){4}$/;

export const PHONE_ERROR = 'Numéro invalide (ex : 06 12 34 56 78 ou +33 6 12 34 56 78)';

export function isValidPhone(value: string): boolean {
  return !value || FR_PHONE_REGEX.test(value.trim());
}
