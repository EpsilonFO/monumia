import 'i18next';

import type { ressourcesFr } from './ressources';

// Les clés sont typées sur les JSON français : une clé absente ne compile pas.
declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'landing';
    resources: typeof ressourcesFr;
  }
}
