import 'i18next';

import type { ressourcesFr } from './ressources';

// Les clés de traduction sont typées sur les JSON français : `t('projets:cle')`
// qui n'existe pas en français ne compile pas.
declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'common';
    resources: typeof ressourcesFr;
  }
}
