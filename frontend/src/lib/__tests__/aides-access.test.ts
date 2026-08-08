import { describe, it, expect } from 'vitest';
import { resolveAidesAccess } from '../aides-access';
import type { BillingAccess } from '@/types';

function access(partial: Partial<BillingAccess> = {}): BillingAccess {
  return {
    allAccess: false,
    unlockedMonumentIds: [],
    subscription: null,
    configured: true,
    testMode: false,
    ...partial,
  };
}

describe('resolveAidesAccess', () => {
  it('verrouille tant que les droits ne sont pas revenus du serveur', () => {
    // Le défaut compte : l'inverse laisserait voir le contenu payant le temps
    // d'un aller-retour réseau, à chaque ouverture de page.
    const result = resolveAidesAccess(null, 'projet-1', false);
    expect(result.locked).toBe(true);
    expect(result.loading).toBe(true);
  });

  it('un échec de chargement laisse tout verrouillé', () => {
    // Le store marque `loaded` sans poser `access` : refuser est le seul repli
    // acceptable quand on ne sait pas.
    const result = resolveAidesAccess(null, 'projet-1', true);
    expect(result.locked).toBe(true);
    expect(result.loading).toBe(false);
  });

  it('verrouille un compte sans aucun droit', () => {
    expect(resolveAidesAccess(access(), 'projet-1', true).locked).toBe(true);
  });

  it('déverrouille le projet payé, et lui seul', () => {
    const paid = access({ unlockedMonumentIds: ['projet-1'] });
    expect(resolveAidesAccess(paid, 'projet-1', true).locked).toBe(false);
    expect(resolveAidesAccess(paid, 'projet-2', true).locked).toBe(true);
  });

  it('un abonnement ouvre tous les projets, y compris jamais vus', () => {
    const abonne = access({ allAccess: true });
    expect(resolveAidesAccess(abonne, 'projet-1', true).locked).toBe(false);
    expect(resolveAidesAccess(abonne, 'projet-jamais-vu', true).locked).toBe(false);
    expect(resolveAidesAccess(abonne, undefined, true).allAccess).toBe(true);
  });

  it('sans projet en contexte, seul un accès global déverrouille', () => {
    // Un écran hors projet ne peut rien conclure d'un déblocage à l'unité.
    const paid = access({ unlockedMonumentIds: ['projet-1'] });
    expect(resolveAidesAccess(paid, undefined, true).locked).toBe(true);
    expect(resolveAidesAccess(access({ allAccess: true }), undefined, true).locked).toBe(false);
  });
});
