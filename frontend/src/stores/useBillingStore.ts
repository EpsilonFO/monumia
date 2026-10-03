import { create } from 'zustand';
import type { BillingAccess } from '@/types';
import { billingService } from '@/services/billing.service';

interface BillingState {
  access: BillingAccess | null;
  loading: boolean;
  /** Passe à true dès la première réponse, même en erreur : évite de boucler. */
  loaded: boolean;

  loadAccess: () => Promise<void>;
  reset: () => void;
}

/**
 * Offres détenues par le compte, servies par le backend.
 *
 * Volontairement NON persisté : contrairement au profil, ces droits ouvrent du
 * contenu payant. Les garder dans le localStorage laisserait n'importe qui
 * s'accorder l'offre Multi-monuments depuis la console du navigateur. Ils sont
 * donc rechargés à chaque ouverture de session — et le serveur reste de toute
 * façon le seul à décider ce qu'il envoie, comme ce qu'il accepte.
 */
export const useBillingStore = create<BillingState>()((set) => ({
  access: null,
  loading: false,
  loaded: false,

  loadAccess: async () => {
    set({ loading: true });
    try {
      set({ access: await billingService.getAccess(), loaded: true });
    } catch (err) {
      // Un échec ne doit pas ouvrir l'accès par accident : `access` reste null,
      // et les hooks retombent sur l'offre gratuite (cf. useOffre).
      console.error('Chargement des droits de facturation impossible', err);
      set({ loaded: true });
    } finally {
      set({ loading: false });
    }
  },

  reset: () => set({ access: null, loading: false, loaded: false }),
}));
