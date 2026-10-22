import i18n from 'i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import { initReactI18next } from 'react-i18next';

import { NAMESPACES, ressourcesFr } from './ressources';

/**
 * Internationalisation du site vitrine, sur le modèle de frontend/src/i18n.
 *
 * Le choix de langue est partagé avec l'application par le cookie
 * `monumia_langue`, posé sur le domaine parent (monumia.fr et app.monumia.fr ne
 * partagent pas leur localStorage). Ordre de détection : `?lang=`, ce cookie, le
 * localStorage, la langue du navigateur. Changer de langue recharge la page.
 */

export const LANGUES = ['fr', 'en'] as const;
export type Langue = (typeof LANGUES)[number];
export const LANGUE_PAR_DEFAUT: Langue = 'fr';

const CLE_STOCKAGE = 'monumia.langue';
const COOKIE = 'monumia_langue';
const PARAMETRE_URL = 'lang';
const UN_AN_EN_MINUTES = 60 * 24 * 365;

const chargeurs = import.meta.glob<{ default: Record<string, unknown> }>([
  './locales/*/*.json',
  '!./locales/fr/*.json',
]);

/** Domaine parent (`monumia.fr`), ou `null` sur localhost / une IP. */
function domaineParent(): string | null {
  const hote = window.location.hostname;
  if (hote === 'localhost' || /^[\d.]+$/.test(hote)) return null;
  const parties = hote.split('.');
  if (parties.length < 2) return null;
  return parties.slice(-2).join('.');
}

async function chargerLangue(langue: Langue): Promise<void> {
  if (langue === LANGUE_PAR_DEFAUT) return;
  await Promise.all(
    NAMESPACES.map(async (ns) => {
      const chargeur = chargeurs[`./locales/${langue}/${ns}.json`];
      if (!chargeur) return;
      const module = await chargeur();
      i18n.addResourceBundle(langue, ns, module.default, true, true);
    }),
  );
}

export function langueCourante(): Langue {
  const langue = i18n.resolvedLanguage ?? i18n.language;
  return (LANGUES as readonly string[]).includes(langue) ? (langue as Langue) : LANGUE_PAR_DEFAUT;
}

/** Locale BCP 47 pour `Intl.*` et `toLocaleString`. */
export function localeIntl(): string {
  return langueCourante() === 'en' ? 'en-GB' : 'fr-FR';
}

/** Langue détectée (`en-GB` → `en`), ramenée aux langues proposées. */
function langueDetectee(): Langue {
  const langue = (i18n.language ?? '').split('-')[0];
  return (LANGUES as readonly string[]).includes(langue) ? (langue as Langue) : LANGUE_PAR_DEFAUT;
}

export async function initialiserI18n(): Promise<void> {
  await i18n
    .use(LanguageDetector)
    .use(initReactI18next)
    .init({
      resources: { fr: ressourcesFr },
      partialBundledLanguages: true,
      fallbackLng: LANGUE_PAR_DEFAUT,
      supportedLngs: LANGUES,
      load: 'languageOnly',
      ns: NAMESPACES,
      defaultNS: 'landing',
      interpolation: { escapeValue: false },
      returnNull: false,
      detection: {
        order: ['querystring', 'cookie', 'localStorage', 'navigator'],
        lookupQuerystring: PARAMETRE_URL,
        lookupCookie: COOKIE,
        lookupLocalStorage: CLE_STOCKAGE,
        caches: ['localStorage', 'cookie'],
        cookieMinutes: UN_AN_EN_MINUTES,
        cookieDomain: domaineParent() ?? undefined,
        cookieOptions: { path: '/', sameSite: 'lax' },
      },
    });

  // `resolvedLanguage` ne retient qu'une langue dont les traductions sont déjà
  // chargées : à ce stade il vaut toujours `fr`. On part donc de la langue
  // DÉTECTÉE, on charge ses traductions, puis on la rend effective.
  const langue = langueDetectee();
  try {
    await chargerLangue(langue);
    if (langue !== LANGUE_PAR_DEFAUT) await i18n.changeLanguage(langue);
  } catch {
    // Traductions introuvables : la page s'affiche en français plutôt que pas du tout.
  }
  document.documentElement.lang = langueCourante();
}

/** Mémorise la langue choisie (cookie partagé avec l'application) et recharge. */
export function changerLangue(langue: Langue): void {
  const domaine = domaineParent();
  document.cookie =
    `${COOKIE}=${langue}; path=/; max-age=${UN_AN_EN_MINUTES * 60}; SameSite=Lax` +
    (domaine ? `; domain=.${domaine}` : '');
  const url = new URL(window.location.href);
  try {
    window.localStorage.setItem(CLE_STOCKAGE, langue);
    url.searchParams.delete(PARAMETRE_URL);
  } catch {
    url.searchParams.set(PARAMETRE_URL, langue);
  }
  window.location.replace(url.toString());
}

export default i18n;
