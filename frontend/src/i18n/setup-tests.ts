// Chargé avant chaque fichier de test (vitest.config.ts) : les libellés calculés
// par lib/, stores/ et services/ passent par i18n, et les tests les assertent en
// français.
import { initialiserI18nPourTests } from './index';

initialiserI18nPourTests();
