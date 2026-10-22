import type { Locale } from 'date-fns';
import { enGB, fr } from 'date-fns/locale';

import { langueCourante, type Langue } from './index';

// Locale de mise en forme de chaque langue de l'interface. L'anglais suit les
// conventions britanniques (« 21 October 2026 », jour avant mois), plus proches
// des usages français que les américaines.
const LOCALE_INTL: Record<Langue, string> = { fr: 'fr-FR', en: 'en-GB' };
const LOCALE_DATE_FNS: Record<Langue, Locale> = { fr, en: enGB };

/** Locale BCP 47 pour `Intl.*`, `toLocaleString`, `toLocaleDateString`. */
export function localeIntl(): string {
  return LOCALE_INTL[langueCourante()];
}

/** Locale date-fns, à passer en `{ locale: localeDateFns() }`. */
export function localeDateFns(): Locale {
  return LOCALE_DATE_FNS[langueCourante()];
}
