import type { ComponentType } from 'react';
import { IconDashboard, IconMonument, IconDocuments } from '@/components/icons';
import { ROUTES } from '@/constants/routes';
import { libelleMonuments, type Offre } from '@/lib/offres';

export interface NavItem {
  to: string;
  icon: ComponentType<{ size?: number; className?: string }>;
  label: string;
  end?: boolean;
  /**
   * Entrée visible mais que l'offre n'ouvre pas : elle mène à la page Tarifs.
   * Les barres de navigation s'en servent pour ne PAS la marquer active — on
   * est alors sur /tarifs, et souligner « Tableau de bord » y annoncerait une
   * page qu'on n'a pas ouverte.
   */
  verrouille?: boolean;
}

/**
 * Navigation principale du propriétaire — peu d'entrées, présentées en barre
 * haute (et repliées en bas sur mobile, cf. BottomNav).
 *
 * Le tableau de bord est réservé à l'offre Multi-monuments : sur un seul
 * monument, il n'agrège rien que la fiche ne montre déjà, et c'est précisément
 * ce que l'offre vend. L'entrée reste pourtant VISIBLE pour tout le monde —
 * une porte plutôt qu'un vide, comme l'onglet Équipe — et pointe alors vers la
 * page Tarifs. Un onglet simplement absent d'une barre de trois ne dit rien de
 * ce qui manque ; il ne se remarque même pas.
 *
 * Le lien mène VRAIMENT où il dit : `to` vaut `/tarifs`, plutôt qu'un `/app`
 * détourné au clic. C'est ce qui fait que le survol, le clic milieu et
 * « copier le lien » racontent la même chose que le clic.
 *
 * Dans un fichier à part de `ownerNav.tsx` : mélanger une fonction utilitaire
 * et un composant dans le même module casse le rafraîchissement à chaud de Vite.
 */
export function navItemsPour(offre: Offre): NavItem[] {
  return [
    offre.dashboard
      ? { to: ROUTES.DASHBOARD, icon: IconDashboard, label: 'Tableau de bord', end: true }
      : { to: ROUTES.TARIFS(), icon: IconDashboard, label: 'Tableau de bord', verrouille: true },
    { to: ROUTES.MONUMENTS, icon: IconMonument, label: libelleMonuments(offre) },
    { to: ROUTES.DOCUMENTS, icon: IconDocuments, label: 'Mes documents' },
  ];
}
