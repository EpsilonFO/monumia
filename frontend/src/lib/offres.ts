/**
 * Les trois offres et ce que chacune ouvre — miroir de `backend/services/offres.py`.
 *
 * Table PURE, sans React ni requête : c'est la décision qui montre ou cache un
 * bouton, elle se teste sans monter un composant. Le serveur reste l'autorité —
 * il renvoie l'offre déjà résolue dans `GET /billing/access` et sur chaque
 * monument — mais le front doit connaître la même table pour deux raisons :
 * afficher un état de repli tant que les droits ne sont pas revenus, et savoir
 * quelle offre proposer quand un bouton manque.
 *
 * Les deux tables doivent rester d'accord. `lib/__tests__/offres.test.ts` fige
 * les mêmes valeurs que `tests/test_billing_access.py` côté serveur : un bouton
 * affiché que le serveur refuse est le pire des deux mondes.
 *
 * À noter, si l'offre gratuite semble introuvable en testant : depuis le
 * 2026-09-07, tout compte NEUF reçoit Multi-monuments d'office (côté serveur,
 * `PLAN_A_LA_CREATION`). GRATUIT reste l'état des comptes créés avant, et le
 * repli du front tant que `GET /billing/access` n'a pas répondu — d'où son
 * maintien ici à l'identique.
 */

import i18n from '@/i18n';

export type BillingPlan = 'veille' | 'multi_monuments';

/**
 * Ce qui s'achète en libre-service. VIDE : les deux offres payantes se
 * négocient, la page Tarifs n'affiche aucun montant et renvoie vers un
 * courrier. Elles restent des offres de plein droit, et Stripe reste l'outil de
 * facturation — c'est seulement le tunnel d'achat qui est fermé.
 *
 * Miroir de `PLANS_VENDABLES` côté serveur, où `POST /billing/checkout` refuse
 * en 409 tout ce qui n'y figure pas. Ouvrir la vente d'une offre se fait des
 * deux côtés à la fois, sinon le bouton promet ce que le serveur refuse.
 */
export const PLANS_VENDABLES: readonly BillingPlan[] = [];

/** Ce qu'un compte (ou un monument) permet. `null` sur un plafond = illimité. */
export interface Offre {
  /** Identifiant, en français comme le serveur l'envoie : à afficher via `libelleOffre`. */
  nom: string;
  /** Monuments que le compte peut enregistrer. */
  monumentsMax: number | null;
  /** Projets par monument. */
  projetsMax: number | null;
  /** Le tableau de bord agrégé (`/app`). */
  dashboard: boolean;
  /** Inviter quelqu'un sur un monument ou sur un de ses chantiers. */
  equipe: boolean;
  suppressionMonument: boolean;
  suppressionProjet: boolean;
  /** Voir en clair les aides dont le guichet n'est pas encore ouvert. */
  aidesBientot: boolean;
  /** L'échéancier d'un projet. */
  echeancier: boolean;
  /** Les emails : ouverture de guichet, rappels avant échéance. */
  rappelsEmail: boolean;
}

export const OFFRE_GRATUITE: Offre = {
  nom: 'Gratuit',
  monumentsMax: 1,
  projetsMax: 2,
  dashboard: false,
  equipe: false,
  suppressionMonument: false,
  suppressionProjet: false,
  aidesBientot: false,
  echeancier: false,
  rappelsEmail: false,
};

export const OFFRE_VEILLE: Offre = {
  ...OFFRE_GRATUITE,
  nom: 'Veille',
  projetsMax: null,
  equipe: true,
  suppressionProjet: true,
  aidesBientot: true,
  echeancier: true,
  rappelsEmail: true,
};

export const OFFRE_MULTI_MONUMENTS: Offre = {
  ...OFFRE_VEILLE,
  nom: 'Multi-monuments',
  monumentsMax: null,
  dashboard: true,
  suppressionMonument: true,
};

const OFFRE_PAR_PLAN: Record<BillingPlan, Offre> = {
  veille: OFFRE_VEILLE,
  multi_monuments: OFFRE_MULTI_MONUMENTS,
};

/**
 * L'offre effective, à partir des plans détenus.
 *
 * Cumuler Veille et Multi-monuments est sans effet utile (le second contient le
 * premier) mais arrive le temps d'une montée en gamme : on prend le meilleur
 * droit de chaque colonne, jamais le premier plan trouvé. Un plan inconnu —
 * abonnement antérieur aux trois offres — n'ouvre rien.
 */
export function offrePour(plans: readonly string[] | undefined | null): Offre {
  const connus = (plans ?? []).filter((p): p is BillingPlan => p in OFFRE_PAR_PLAN);
  if (connus.length === 0) return OFFRE_GRATUITE;
  if (connus.length === 1) return OFFRE_PAR_PLAN[connus[0]];

  const offres = connus.map((p) => OFFRE_PAR_PLAN[p]);
  return {
    nom: offres.some((o) => o.monumentsMax === null) ? 'Multi-monuments' : 'Veille',
    monumentsMax: plafondMax(offres.map((o) => o.monumentsMax)),
    projetsMax: plafondMax(offres.map((o) => o.projetsMax)),
    dashboard: offres.some((o) => o.dashboard),
    equipe: offres.some((o) => o.equipe),
    suppressionMonument: offres.some((o) => o.suppressionMonument),
    suppressionProjet: offres.some((o) => o.suppressionProjet),
    aidesBientot: offres.some((o) => o.aidesBientot),
    echeancier: offres.some((o) => o.echeancier),
    rappelsEmail: offres.some((o) => o.rappelsEmail),
  };
}

/**
 * Comment nommer l'espace « monuments » dans l'interface.
 *
 * Au singulier tant que l'offre ne permet qu'un bien (Gratuit, Veille) : « Mes
 * monuments » promettrait une collection que le compte ne peut pas avoir. C'est
 * le plafond qui décide, pas le nombre de biens enregistrés — un abonné
 * Multi-monuments qui n'en a qu'un garde le pluriel.
 *
 * Le seul libellé de cette table : il n'a pas de miroir côté serveur, mais il
 * se déduit du plafond, donc il vit ici plutôt que recopié dans six écrans.
 */
export function libelleMonuments(offre: Offre): string {
  return offre.monumentsMax === 1 ? i18n.t('core:offres.monMonument') : i18n.t('core:offres.mesMonuments');
}

/**
 * Le nom d'une offre tel qu'il s'affiche (« Veille » → « Watch » en anglais).
 *
 * `Offre.nom` reste un IDENTIFIANT : le serveur l'envoie en français, et
 * `estOffreGratuite` le compare. Il ne se traduit donc qu'à l'affichage, ici.
 * Un nom inconnu s'affiche tel quel.
 */
export function libelleOffre(nom: string): string {
  if (nom === OFFRE_GRATUITE.nom) return i18n.t('core:offres.noms.gratuit');
  if (nom === OFFRE_VEILLE.nom) return i18n.t('core:offres.noms.veille');
  if (nom === OFFRE_MULTI_MONUMENTS.nom) return i18n.t('core:offres.noms.multiMonuments');
  return nom;
}

/**
 * Le compte (ou le monument) est-il resté sur l'offre gratuite ?
 *
 * Prédicat d'AFFICHAGE, pas un droit : il ne garde aucune action, il choisit ce
 * qu'une page met en avant. Il n'a donc pas de miroir côté serveur, et rien de
 * ce qu'il masque n'est retenu — même idiome que `libelleMonuments`. Un droit
 * qui refuse quelque chose se pose dans `Offre`, où le serveur le tient aussi.
 */
export function estOffreGratuite(offre: Offre): boolean {
  return offre.nom === OFFRE_GRATUITE.nom;
}

/** Le plus permissif de plusieurs plafonds ; `null` (illimité) l'emporte. */
function plafondMax(valeurs: (number | null)[]): number | null {
  return valeurs.includes(null) ? null : Math.max(...(valeurs as number[]));
}

/**
 * Reste-t-il de la place sous un plafond ?
 *
 * `null` = illimité, d'où le helper plutôt qu'une comparaison recopiée à chaque
 * bouton — `undefined >= null` et `2 >= null` mentent tous les deux en
 * JavaScript.
 */
export function sousLePlafond(plafond: number | null, deja: number): boolean {
  return plafond === null || deja < plafond;
}
