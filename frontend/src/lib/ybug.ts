/**
 * Widget de retour utilisateur Ybug (https://ybug.io) : le testeur capture son
 * écran, l'annote, commente — le rapport part chez Ybug avec l'URL, le
 * navigateur, la console, et les données jointes ici. Branché pour la phase de
 * bêta-test.
 *
 * Ce module est PUR : il dit si le widget doit se charger et avec quelles
 * données. L'injection du script et les appels au widget vivent dans
 * `components/shared/YbugWidget.tsx`.
 */

import type { BillingPlan, User } from '@/types';

/**
 * Ce qu'on joint à chaque rapport. Les clés sont libres côté Ybug (« any other
 * info you need to add context ») ; seul `id` a un sens pour lui — c'est la clé
 * d'identification d'un utilisateur, nulle pour un visiteur anonyme.
 *
 * L'email y passe de propos délibéré : un rapport de bêta-test sans moyen de
 * recontacter son auteur ne vaut pas grand-chose. Rien d'autre du compte n'y
 * va — ni token, ni monument, ni document.
 */
export interface YbugUser {
  /** `null` hors session : Ybug compte alors un visiteur, pas le dernier connecté. */
  id?: string | null;
  username?: string;
  email?: string;
  /** Les offres détenues, pour lire un rapport à la lumière de ce qui est ouvert. */
  offres?: string;
  admin?: boolean;
}

/**
 * L'identifiant du projet Ybug, ou `undefined` si le widget ne doit pas se
 * charger. C'est le seul interrupteur : sans `VITE_YBUG_ID` (développement
 * local, tests, build d'un environnement sans widget), pas de script, pas de
 * bouton, aucune requête vers ybug.io.
 */
export function idProjetYbug(): string | undefined {
  // Accès littéral : Vite ne substitue `import.meta.env.X` qu'écrit en clair.
  const id = (import.meta.env.VITE_YBUG_ID as string | undefined)?.trim();
  return id ? id : undefined;
}

/**
 * Les données jointes aux rapports pour l'utilisateur courant.
 *
 * `plans` vient de `GET /billing/access` : `undefined` tant qu'il n'a pas
 * répondu (on n'annonce alors aucune offre, plutôt que d'annoncer à tort
 * « gratuit »), tableau vide = offre gratuite.
 */
export function contexteYbug(
  user: User | null,
  plans: readonly BillingPlan[] | undefined
): YbugUser {
  if (!user) return { id: null };

  const nom = [user.prenom, user.nom].filter(Boolean).join(' ').trim();
  const contexte: YbugUser = {
    id: user.id,
    username: nom || user.email,
    email: user.email,
    admin: Boolean(user.estAdmin),
  };
  if (plans) contexte.offres = plans.length > 0 ? plans.join(', ') : 'gratuit';
  return contexte;
}
