// Ressources françaises, embarquées : langue par défaut, langue de repli, et base
// du typage des clés (cf. i18next.d.ts). Les autres langues se chargent à la demande.
import landing from './locales/fr/landing.json';
import legal from './locales/fr/legal.json';

export const ressourcesFr = { landing, legal };

export type Namespace = keyof typeof ressourcesFr;

export const NAMESPACES = Object.keys(ressourcesFr) as Namespace[];
