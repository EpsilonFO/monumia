import type { NomPicto } from '@/components/shared/ecrans/Picto';
import i18n from '@/i18n';
import { ROUTES } from '@/constants/routes';
import { libelleMonuments, type Offre } from '@/lib/offres';

export interface NavItem {
  to: string;
  picto: NomPicto;
  label: string;
  /** Libellé de la barre du bas : quatre onglets y tiennent dans 400 px. */
  court?: string;
  end?: boolean;
  /** Infobulle, quand le libellé ne dit pas à quoi sert l'entrée. */
  title?: string;
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
    {
      to: ROUTES.DASHBOARD,
      picto: 'grille',
      label: i18n.t('shell:navigation.tableauDeBord'),
      court: i18n.t('shell:navigation.accueil'),
      end: true,
    },
    {
      to: ROUTES.MONUMENTS,
      picto: 'maison',
      label: libelleMonuments(offre),
      court: offre.monumentsMax === 1 ? i18n.t('shell:navigation.monument') : i18n.t('shell:navigation.monuments'),
    },
    {
      to: ROUTES.DOCUMENTS,
      picto: 'doc',
      label: i18n.t('shell:navigation.mesDocuments'),
      court: i18n.t('shell:navigation.documents'),
      title: i18n.t('shell:navigation.documentsTitre'),
    },
  ];
}

/**
 * Le Blog, public (ressources) : ajouté après la nav privée, dans la barre
 * haute comme dans la barre du bas, pour que le mobile ne le perde pas.
 */
export const NAV_BLOG: NavItem = {
  to: '/blog',
  picto: 'livre',
  // Getter : lu au rendu, dans la langue de la page (jamais traduit à l'import).
  get label() {
    return i18n.t('shell:navigation.blog');
  },
};
