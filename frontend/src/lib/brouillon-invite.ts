import i18n from '@/i18n';
import { useBrouillonInviteStore } from '@/stores/useBrouillonInviteStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useProjetStore } from '@/stores/useProjetStore';
import { monumentService } from '@/services/monument.service';
import { projetService } from '@/services/projet.service';
import { questionnaireDeCadrage } from '@/constants/raisons';
import type { Monument, MonumentInput } from '@/types';

/**
 * Le rejeu du brouillon découverte : de ce qu'un visiteur a décrit sans compte
 * à un monument et un projet bien réels.
 *
 * Module PUR de composants (tout passe par `getState()`), donc testable en
 * environnement node — `vitest.config.ts` n'a pas de DOM.
 */

/** Le brouillon est-il complet, donc rejouable ?
 *
 *  `etape === 'inscription'` compte autant que la présence du monument : un
 *  brouillon abandonné à l'étape des travaux ne doit pas se rejouer tout seul
 *  au prochain retour de Google. */
export function brouillonPretPourRejeu(): boolean {
  const { monument, etape } = useBrouillonInviteStore.getState();
  return monument !== null && etape === 'inscription';
}

/**
 * Le brouillon vu comme un `Monument`, pour la mini-fiche du rail du wizard.
 *
 * `id: 'brouillon'` est un marqueur, pas un identifiant : rien de ce qui
 * affiche cet objet ne le suit (le rail ne montre que nom, commune et
 * protection). Aucun appel réseau ne doit le prendre pour cible.
 */
export function monumentDepuisBrouillon(m: MonumentInput): Monument {
  const maintenant = new Date().toISOString();
  return {
    ...m,
    id: 'brouillon',
    userId: '',
    photos: [],
    completionPercentage: 0,
    createdAt: maintenant,
    updatedAt: maintenant,
  };
}

/**
 * Intention « Google cliqué depuis le parcours découverte », mise de côté le
 * temps de l'aller-retour OAuth.
 *
 * Même patron que `lib/pending-invitation.ts` : le flux quitte l'application,
 * un store en mémoire ne survivrait pas et l'URL de retour est imposée par la
 * liste blanche Supabase. `sessionStorage`, donc, borné à l'onglet.
 *
 * Ce drapeau porte l'INTENTION, et c'est tout son intérêt : sans lui, une
 * connexion Google ordinaire déclencherait le rejeu d'un vieux brouillon oublié
 * dans le `localStorage`.
 */
const CLE_RETOUR_GOOGLE = 'monumia_retour_brouillon';

export function marquerRetourGoogleBrouillon(): void {
  try {
    sessionStorage.setItem(CLE_RETOUR_GOOGLE, '1');
  } catch {
    // Navigation privée ou stockage saturé : le retour Google atterrira sur
    // l'espace, et le brouillon reste reprenable depuis le wizard.
  }
}

export function prendreRetourGoogleBrouillon(): boolean {
  try {
    const marque = sessionStorage.getItem(CLE_RETOUR_GOOGLE);
    if (marque) sessionStorage.removeItem(CLE_RETOUR_GOOGLE);
    return marque !== null;
  } catch {
    return false;
  }
}

/**
 * Crée pour de vrai le monument puis le projet du brouillon, et amorce les
 * stores.
 *
 * Non atomique — deux écritures, pas de transaction — d'où les identifiants
 * posés dans le brouillon AU FUR ET À MESURE : si le projet échoue, un
 * « Réessayer » ne rejoue que lui, et le compte ne se retrouve pas avec deux
 * monuments (le second serait d'ailleurs refusé en 402 au gratuit).
 *
 * Les `ApiError` remontent telles quelles : c'est l'écran de reprise qui
 * tranche sur le statut (402 offre, 422 brouillon périmé, le reste
 * « Réessayer »), lui seul sait quoi en dire.
 */
export async function finaliserBrouillon(): Promise<{ monumentId: string; projetId: string }> {
  // Deux onglets ouverts sur le parcours : celui-ci peut avoir un état plus
  // ancien que ce que l'autre a écrit. On relit le stockage avant d'agir.
  await useBrouillonInviteStore.persist.rehydrate();

  const brouillon = useBrouillonInviteStore.getState();
  if (!brouillon.monument) {
    throw new Error(i18n.t('core:brouillonInvite.aucunBrouillon'));
  }

  const monument = brouillon.monumentId
    ? await monumentService.getById(brouillon.monumentId)
    : await monumentService.create(brouillon.monument);
  // Immédiatement, avant l'appel suivant : c'est ce qui rend « Réessayer »
  // sans effet de bord.
  useBrouillonInviteStore.getState().marquerMonumentCree(monument.id);

  const projet = brouillon.projetId
    ? await projetService.getById(brouillon.projetId)
    : await projetService.create(monument.id, {
        // `[]` est une valeur valide (« Pas encore déterminé ») : le tri-state
        // du brouillon se ramène ici à ce que la colonne accepte.
        travauxEnvisages: brouillon.travaux ?? [],
        // Le cadrage entier est recomposé depuis ses sources uniques (le
        // brouillon ne stocke pas les clés réservées dans `answers`).
        // `familles` à `null` veut dire « question non posée » : la clé reste
        // alors absente, ce qui n'est pas la même chose qu'une liste vide.
        questionnaire: questionnaireDeCadrage(
          brouillon.answers,
          brouillon.raisons,
          brouillon.familles,
        ),
      });
  useBrouillonInviteStore.getState().marquerProjetCree(projet.id);

  useMonumentStore.getState().upsertMonument(monument);
  useMonumentStore.getState().setActiveMonument(monument.id);
  useProjetStore.getState().upsertProjet(projet);

  useBrouillonInviteStore.getState().vider();
  return { monumentId: monument.id, projetId: projet.id };
}
