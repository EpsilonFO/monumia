import type { NomPicto } from '@/components/shared/ecrans/Picto';
import { ROUTES } from '@/constants/routes';
import { libelleMonuments, type Offre } from '@/lib/offres';

export interface NavItem {
  to: string;
  picto: NomPicto;
  label: string;
  end?: boolean;
}

/**
 * Navigation principale du propriétaire — peu d'entrées, présentées en barre
 * haute (et repliées en bas sur mobile, cf. BottomNav).
 *
 * Les trois entrées sont visibles pour tout le monde, et mènent toutes où elles
 * disent. Le tableau de bord est réservé à l'offre Multi-monuments, mais ce
 * n'est PAS la navigation qui le garde : la page s'ouvre, floutée, avec le
 * paywall devant (cf. DashboardRoute). Un onglet absent ne dit rien de ce qui
 * manque, et un onglet détourné vers les tarifs mentirait sur sa destination.
 *
 * Dans un fichier à part de `ownerNav.tsx` : mélanger une fonction utilitaire
 * et un composant dans le même module casse le rafraîchissement à chaud de Vite.
 */
export function navItemsPour(offre: Offre): NavItem[] {
  return [
    { to: ROUTES.DASHBOARD, picto: 'grille', label: 'Tableau de bord', end: true },
    { to: ROUTES.MONUMENTS, picto: 'maison', label: libelleMonuments(offre) },
    { to: ROUTES.DOCUMENTS, picto: 'doc', label: 'Mes documents' },
  ];
}
