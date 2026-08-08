/** Offres payantes et droits d'accès (Stripe). */

export type BillingPlan = 'dossier' | 'abonnement';

/** Un prix tel qu'il est configuré dans Stripe — jamais recopié côté front. */
export interface BillingPrice {
  plan: BillingPlan;
  priceId: string;
  amountCents: number | null;
  currency: string;
  /** 'month' pour l'abonnement, null pour un paiement unique. */
  interval: string | null;
  recurring: boolean;
}

export interface BillingPlansResponse {
  /** false = Stripe n'est pas branché : la page Tarifs affiche son état d'attente. */
  configured: boolean;
  testMode?: boolean;
  plans: BillingPrice[];
}

export interface BillingSubscription {
  status: string;
  currentPeriodEnd: string | null;
  cancelAtPeriodEnd: boolean;
}

/**
 * Droits du compte, tels que le serveur les calcule. C'est la seule autorité :
 * le profil persisté dans le localStorage ne débloque rien.
 */
export interface BillingAccess {
  /** Abonnement actif ou accès accordé manuellement → tous les projets ouverts. */
  allAccess: boolean;
  /** Projets débloqués à l'unité. Vide quand `allAccess` est vrai. */
  unlockedMonumentIds: string[];
  subscription: BillingSubscription | null;
  configured: boolean;
  testMode: boolean;
}
