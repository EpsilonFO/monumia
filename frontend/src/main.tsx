import './index.css'
import { initialiserI18n } from './i18n'
import { rechargerSurMorceauPerdu } from './lib/morceau-perdu'

rechargerSurMorceauPerdu()

// La langue (et, hors français, ses traductions) doit être prête avant que le
// reste de l'application ne s'évalue : elle est fixe pour la durée de vie de la
// page (cf. src/i18n), et un libellé calculé à l'import serait sinon figé en
// français. D'où l'import différé de tout le reste.
void initialiserI18n()
  .then(() => import('./demarrage'))
  .then(({ demarrer }) => demarrer())
