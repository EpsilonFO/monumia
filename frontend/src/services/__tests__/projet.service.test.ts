import { describe, expect, it } from 'vitest';
import { toProjet } from '@/services/projet.service';

describe('toProjet', () => {
  it('mappe les colonnes snake_case', () => {
    const projet = toProjet({
      id: 'p1',
      monument_id: 'm1',
      user_id: 'u1',
      titre: 'Toiture',
      travaux_envisages: ['toiture', 'charpente'],
      questionnaire: { fait_x: 'oui' },
      cloture_at: '2026-01-01T00:00:00Z',
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-06-01T00:00:00Z',
    });

    expect(projet).toEqual({
      id: 'p1',
      monumentId: 'm1',
      userId: 'u1',
      titre: 'Toiture',
      travauxEnvisages: ['toiture', 'charpente'],
      questionnaire: { fait_x: 'oui' },
      clotureAt: '2026-01-01T00:00:00Z',
      createdAt: '2025-01-01T00:00:00Z',
      updatedAt: '2025-06-01T00:00:00Z',
    });
  });

  describe('tri-state des travaux', () => {
    it('une liste vide reste une liste vide (« Pas encore déterminé »)', () => {
      // Ne JAMAIS la ramener à null : c'est une réponse explicite, qui rend le
      // hard_filter travaux du moteur fail-open.
      expect(toProjet({ travaux_envisages: [] }).travauxEnvisages).toEqual([]);
    });

    it('une clé absente vaut « jamais répondu »', () => {
      expect(toProjet({}).travauxEnvisages).toBeNull();
    });

    it('un null explicite vaut « jamais répondu »', () => {
      expect(toProjet({ travaux_envisages: null }).travauxEnvisages).toBeNull();
    });
  });

  describe('questionnaire', () => {
    it('préserve les clés réservées « _ » telles quelles', () => {
      // Elles repartent au backend à chaque diagnostic, qui les isole lui-même.
      const q = toProjet({
        questionnaire: { _raisons: ['fiscalite', 'etude_ingenierie'], fait_y: ['a', 'b'] },
      }).questionnaire;
      expect(q._raisons).toEqual(['fiscalite', 'etude_ingenierie']);
      expect(q.fait_y).toEqual(['a', 'b']);
    });

    it('un questionnaire absent devient un objet vide, jamais undefined', () => {
      expect(toProjet({}).questionnaire).toEqual({});
    });
  });

  it('un titre absent reste undefined (le front le dérive des travaux)', () => {
    expect(toProjet({ id: 'p1' }).titre).toBeUndefined();
  });
});
