import i18n from 'i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import { initReactI18next } from 'react-i18next';

import { apexDomain } from '@/lib/session';

import { NAMESPACES, ressourcesFr } from './ressources';

/**
 * Internationalisation de l'application.
 *
 * - Le français est la langue par défaut et la langue de repli : une clé absente
 *   d'une autre langue s'affiche en français plutôt qu'en clé brute.
 * - La langue se détecte dans cet ordre : `?lang=` dans l'URL, puis le cookie
 *   `monumia_langue` posé sur le domaine parent (partagé avec le site vitrine, les
 *   deux origines ne partagent pas leur localStorage), puis le choix mémorisé dans
 *   ce navigateur, puis la langue du navigateur.
 * - La langue est FIXE pour la durée de vie de la page : en changer recharge la
 *   page (`changerLangue`). Les libellés calculés hors React (lib, stores,
 *   services) restent ainsi justes sans abonnement à l'événement de changement.
 *
 * Règle d'usage : ne jamais appeler `t` au niveau module (constante calculée à
 * l'import), toujours au moment du rendu ou de l'appel.
 */

export const LANGUES = ['fr', 'en'] as const;
export type Langue = (typeof LANGUES)[number];
export const LANGUE_PAR_DEFAUT: Langue = 'fr';

const CLE_STOCKAGE = 'monumia.langue';
const COOKIE = 'monumia_langue';
const PARAMETRE_URL = 'lang';
const UN_AN_EN_MINUTES = 60 * 24 * 365;

// Les langues autres que le français, chargées à la demande (un morceau par fichier).
const chargeurs = import.meta.glob<{ default: Record<string, unknown> }>([
  './locales/*/*.json',
  '!./locales/fr/*.json',
]);

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
      defaultNS: 'common',
      interpolation: { escapeValue: false },
      returnNull: false,
      detection: {
        order: ['querystring', 'cookie', 'localStorage', 'navigator'],
        lookupQuerystring: PARAMETRE_URL,
        lookupCookie: COOKIE,
        lookupLocalStorage: CLE_STOCKAGE,
        caches: ['localStorage', 'cookie'],
        cookieMinutes: UN_AN_EN_MINUTES,
        cookieDomain: apexDomain() ?? undefined,
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
    // Morceau de traduction introuvable (déploiement en cours, réseau coupé) :
    // la page s'affiche en français plutôt que de ne pas s'afficher.
  }
  document.documentElement.lang = langueCourante();
  retirerParametreUrl();
}

// Le détecteur a mémorisé la langue de `?lang=` : le paramètre n'a plus à traîner
// dans l'URL (ni à être recopié dans un lien partagé).
function retirerParametreUrl(): void {
  try {
    if (window.localStorage.getItem(CLE_STOCKAGE) === null) return;
    const url = new URL(window.location.href);
    if (!url.searchParams.has(PARAMETRE_URL)) return;
    url.searchParams.delete(PARAMETRE_URL);
    window.history.replaceState(window.history.state, '', url.toString());
  } catch {
    // Stockage bloqué : le paramètre reste, c'est lui qui porte la langue.
  }
}

/** Initialisation synchrone en français, pour les tests (environnement node). */
export function initialiserI18nPourTests(): void {
  if (i18n.isInitialized) return;
  void i18n.use(initReactI18next).init({
    resources: { fr: ressourcesFr },
    lng: LANGUE_PAR_DEFAUT,
    fallbackLng: LANGUE_PAR_DEFAUT,
    ns: NAMESPACES,
    defaultNS: 'common',
    interpolation: { escapeValue: false },
    returnNull: false,
    initAsync: false,
  });
}

/** Mémorise la langue choisie et recharge la page dans cette langue. */
export function changerLangue(langue: Langue): void {
  const url = new URL(window.location.href);
  const domaine = apexDomain();
  document.cookie =
    `${COOKIE}=${langue}; path=/; max-age=${UN_AN_EN_MINUTES * 60}; SameSite=Lax` +
    (domaine ? `; domain=.${domaine}` : '');
  try {
    window.localStorage.setItem(CLE_STOCKAGE, langue);
    url.searchParams.delete(PARAMETRE_URL);
  } catch {
    // Stockage bloqué : le paramètre d'URL porte le choix pour ce chargement.
    url.searchParams.set(PARAMETRE_URL, langue);
  }
  window.location.replace(url.toString());
}

export default i18n;
