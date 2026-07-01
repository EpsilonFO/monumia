import { describe, it, expect } from 'vitest';
import { jalonState, montantTileMode } from '../project-card-view';
import type { ProjectStats } from '../project-stats';

function stats(partial: Partial<ProjectStats>): ProjectStats {
  return {
    aidesIdentifiees: 0,
    montantPotentiel: 0,
    dossiersActifs: 0,
    prochaineEcheance: null,
    completion: 0,
    ...partial,
  };
}

describe('jalonState', () => {
  it('marque les etapes precedentes comme franchies', () => {
    expect(jalonState(0, 2)).toBe('done');
    expect(jalonState(1, 2)).toBe('done');
  });
  it("marque l'etape atteinte comme en cours", () => {
    expect(jalonState(2, 2)).toBe('current');
  });
  it('marque les etapes suivantes comme a venir', () => {
    expect(jalonState(3, 2)).toBe('upcoming');
  });
  it('sans etape atteinte (-1), tout est a venir', () => {
    expect(jalonState(0, -1)).toBe('upcoming');
    expect(jalonState(3, -1)).toBe('upcoming');
  });
});

describe('montantTileMode', () => {
  it('nudge quand stats absent', () => {
    expect(montantTileMode(undefined)).toBe('nudge');
  });
  it('nudge quand aucune aide', () => {
    expect(montantTileMode(stats({ aidesIdentifiees: 0 }))).toBe('nudge');
  });
  it('count quand des aides mais montant a zero', () => {
    expect(montantTileMode(stats({ aidesIdentifiees: 2, montantPotentiel: 0 }))).toBe('count');
  });
  it('money quand montant superieur a zero', () => {
    expect(montantTileMode(stats({ aidesIdentifiees: 3, montantPotentiel: 24000 }))).toBe('money');
  });
});
