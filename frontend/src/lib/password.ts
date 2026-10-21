import i18n from '@/i18n';

/**
 * Politique de mot de passe de l'application — volontairement simple et identique
 * partout (inscription générale ET inscription via lien de collaboration) :
 * au moins 8 caractères et au moins 1 chiffre.
 */
export interface PasswordChecks {
  length: boolean;
  number: boolean;
}

export function passwordChecks(password: string): PasswordChecks {
  return {
    length: password.length >= 8,
    number: /\d/.test(password),
  };
}

export function isPasswordValid(password: string): boolean {
  const c = passwordChecks(password);
  return c.length && c.number;
}

/** Critères affichés à l'utilisateur, dans l'ordre. */
export const PASSWORD_RULES: { key: keyof PasswordChecks; label: string }[] = [
  { key: 'length', get label() { return i18n.t('core:password.longueur'); } },
  { key: 'number', get label() { return i18n.t('core:password.chiffre'); } },
];
