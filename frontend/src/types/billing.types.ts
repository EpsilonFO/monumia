/** Offres payantes et droits du compte (Stripe). */

import type { BillingPlan, Offre } from '@/lib/offres';

export type { BillingPlan, Offre };

/** Un prix tel qu'il est configuré dans Stripe — jamais recopié côté front. */
export interface BillingPrice {
  plan: BillingPlan;
  priceId: string;
  amountCents: number | null;
  currency: string;
  /** 'month' : les deux offres sont des abonnements mensuels. */
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
  /** null pour un abonnement antérieur aux trois offres, qui n'ouvre rien. */
  plan: BillingPlan | null;
  status: string;
  currentPeriodEnd: string | null;
  cancelAtPeriodEnd: boolean;
}

/**
 * Droits du compte, tels que le serveur les calcule. C'est la seule autorité :
 * le profil persisté dans le localStorage ne débloque rien.
 */
export interface BillingAccess {
  /** Les offres détenues. Vide = offre gratuite. */
  plans: BillingPlan[];
  /**
   * L'offre déjà résolue par le serveur. Le front tient la même table
   * (`lib/offres.ts`) mais lit CELLE-CI : c'est le serveur qui tranche.
   */
  offre: Offre;
  subscription: BillingSubscription | null;
  /**
   * Le portail Stripe est-il utilisable ? Vrai seulement si le compte est
   * rattaché à un Customer, ce qui ne se déduit PAS de la présence d'une
   * offre : Multi-monuments se négocie et peut être ouverte sans Stripe.
   */
  portail: boolean;
  configured: boolean;
  testMode: boolean;
}
