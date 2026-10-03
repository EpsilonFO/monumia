import type { BillingAccess, BillingPlan, BillingPlansResponse } from '@/types';
import { authFetch, handleResponse } from '@/lib/auth-fetch';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export const billingService = {
  /**
   * Offres et prix. Endpoint public (la page Tarifs se consulte déconnecté),
   * d'où le `fetch` nu plutôt que `authFetch`.
   */
  async getPlans(): Promise<BillingPlansResponse> {
    const res = await fetch(`${BASE}/billing/plans`);
    return handleResponse<BillingPlansResponse>(res);
  },

  async getAccess(): Promise<BillingAccess> {
    const res = await authFetch(`${BASE}/billing/access`);
    return handleResponse<BillingAccess>(res);
  },

  /**
   * Ouvre une session de paiement et renvoie l'URL Stripe où rediriger.
   *
   * Aucun montant n'est envoyé : le serveur choisit le prix à partir du nom de
   * l'offre. Les deux offres sont des abonnements de compte, donc rien d'autre
   * à transmettre — aucun monument n'est débloqué en particulier.
   */
  async startCheckout(plan: BillingPlan): Promise<string> {
    const res = await authFetch(`${BASE}/billing/checkout`, {
      method: 'POST',
      body: JSON.stringify({ plan }),
    });
    const { url } = await handleResponse<{ url: string }>(res);
    return url;
  },

  /** Portail Stripe : factures, moyen de paiement, résiliation. */
  async openPortal(): Promise<string> {
    const res = await authFetch(`${BASE}/billing/portal`, { method: 'POST' });
    const { url } = await handleResponse<{ url: string }>(res);
    return url;
  },
};
