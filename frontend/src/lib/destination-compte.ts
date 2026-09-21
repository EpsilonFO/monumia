import { ROUTES } from '@/constants/routes';
import type { Offre } from '@/lib/offres';

/**
 * Où atterrit quelqu'un qui clique « Mon compte » depuis la landing.
 *
 * La landing (monumia.fr) et l'application (app.monumia.fr) sont deux origines
 * distinctes : la première sait seulement qu'une session existe (cookie de
 * présence, cf. `lib/session.ts`), jamais quelle offre ni quels monuments.
 * C'est donc l'application qui tranche, sur `/mon-compte`, et cette fonction
 * porte toute la décision — pure, donc figée par un test plutôt que vérifiée à
 * la main dans trois états de compte.
 *
 * L'échelle, du plus riche au dernier recours :
 *
 * 1. le tableau de bord quand l'offre l'ouvre (Multi-monuments) : c'est la vue
 *    qui a du sens dès qu'il y a plusieurs biens ;
 * 2. la fiche du monument quand il n'y en a qu'un — le tableau de bord
 *    n'agrégerait rien qu'elle ne montre déjà, et il serait flouté ;
 * 3. la liste quand il y en a plusieurs sans l'offre (un collaborateur invité
 *    sur plusieurs biens) : choisir pour lui serait arbitraire ;
 * 4. le wizard d'enregistrement, faute de bien à montrer.
 *
 * Le dernier recours ne vaut PAS pour un collaborateur : son compte n'est pas
 * fait pour enregistrer un bien, et un partage retiré le renverrait créer un
 * monument plutôt que constater qu'il n'en a plus. Même convention que
 * `RootRedirect` et que la page de connexion.
 */
export function destinationCompte({
  offre,
  monumentIds,
  accountType,
}: {
  offre: Offre;
  monumentIds: readonly string[];
  accountType?: 'proprietaire' | 'collaborateur';
}): string {
  if (offre.dashboard) return ROUTES.DASHBOARD;
  if (monumentIds.length === 1) return ROUTES.MONUMENT_DETAIL(monumentIds[0]);
  if (monumentIds.length > 1) return ROUTES.MONUMENTS;
  return accountType === 'collaborateur' ? ROUTES.MONUMENTS : ROUTES.MONUMENT_NEW;
}
