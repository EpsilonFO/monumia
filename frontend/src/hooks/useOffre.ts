import { useBillingStore } from '@/stores/useBillingStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { OFFRE_GRATUITE, type Offre } from '@/lib/offres';

/**
 * L'offre du COMPTE : ce qui relève de l'abonné lui-même — enregistrer un
 * monument de plus, ouvrir le tableau de bord, recevoir les emails.
 *
 * Retombe sur l'offre gratuite tant que les droits ne sont pas revenus du
 * serveur, ou si leur chargement a échoué : montrer d'abord puis cacher
 * laisserait clignoter du contenu payant à chaque ouverture de page.
 */
export function useOffre(): Offre {
  return useBillingStore((s) => s.access?.offre) ?? OFFRE_GRATUITE;
}

/** Les droits sont-ils revenus du serveur ? Sert aux gardes de redirection. */
export function useOffreChargee(): boolean {
  return useBillingStore((s) => s.loaded);
}

/**
 * L'offre qui gouverne un MONUMENT : ses projets, son calendrier, sa
 * suppression. Le serveur la pose sur chaque monument (union de l'offre du
 * propriétaire et de celle de l'appelant), donc un collaborateur invité par un
 * client abonné garde ce que son client paye.
 *
 * Sans monument (page hors bien) ou avant le premier aller-retour serveur :
 * offre gratuite, par la même prudence que ci-dessus.
 */
export function useOffreMonument(monumentId: string | undefined): Offre {
  return (
    useMonumentStore((s) => s.monuments.find((m) => m.id === monumentId)?.offre) ?? OFFRE_GRATUITE
  );
}
