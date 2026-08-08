import type { BillingAccess } from '@/types';

export interface AidesAccess {
  /** Le détail des aides de ce projet est masqué. */
  locked: boolean;
  /** Un abonnement (ou un accès accordé manuellement) ouvre tous les projets. */
  allAccess: boolean;
  /** Les droits ne sont pas encore revenus du serveur. */
  loading: boolean;
}

/**
 * Résout l'accès au détail des aides d'un projet. Fonction pure — c'est la
 * décision qui ouvre du contenu payant, elle se teste sans React.
 *
 * L'accès se gagne de deux façons : le déblocage à l'unité d'un projet (offre
 * « Dossier ») ou un abonnement, qui les ouvre tous. Sans `monumentId`, seul le
 * second peut répondre — un écran hors projet ne peut rien conclure d'un
 * déblocage à l'unité.
 *
 * Verrouillé par défaut tant que `access` est absent (droits non chargés, ou
 * chargement en échec) : montrer d'abord puis masquer laisserait fuiter le
 * contenu payant à chaque ouverture de page.
 */
export function resolveAidesAccess(
  access: BillingAccess | null,
  monumentId: string | undefined,
  loaded: boolean
): AidesAccess {
  const allAccess = access?.allAccess ?? false;
  const unlocked =
    allAccess || (!!monumentId && !!access?.unlockedMonumentIds.includes(monumentId));

  return { locked: !unlocked, allAccess, loading: !loaded };
}
