import i18n from '@/i18n';

/**
 * Validation d'un numéro de téléphone français, tolérante sur la mise en forme :
 * indicatif +33 / 0033 / 0, puis un chiffre non nul, puis quatre paires
 * éventuellement séparées par un espace, un point ou un tiret.
 *
 * Le champ étant optionnel partout, la chaîne vide est valide.
 */
const FR_PHONE_REGEX = /^(?:\+33|0033|0)[1-9](?:[\s.-]?\d{2}){4}$/;

/** Le message d'erreur d'un numéro invalide, dans la langue de l'interface. */
export function phoneError(): string {
  return i18n.t('core:phone.invalide');
}

/**
 * @deprecated Utiliser `phoneError()`. Gardée pour les appelants existants :
 * calculée à l'import, elle n'est juste que parce que l'application ne
 * s'évalue qu'après l'initialisation d'i18n (cf. main.tsx).
 */
export const PHONE_ERROR = phoneError();

export function isValidPhone(value: string): boolean {
  return !value || FR_PHONE_REGEX.test(value.trim());
}
