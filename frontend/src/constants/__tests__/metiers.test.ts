import { describe, it, expect } from 'vitest';
import { METIER_FAMILLES } from '../metiers';

describe('METIER_FAMILLES', () => {
  it('expose exactement 6 familles', () => {
    expect(METIER_FAMILLES).toHaveLength(6);
  });

  it('place « Autre » en dernier', () => {
    expect(METIER_FAMILLES[METIER_FAMILLES.length - 1]).toBe('Autre');
  });

  it('contient des familles lisibles, sans sous-listes', () => {
    expect(METIER_FAMILLES).toContain('Propriétaire ou porteur du projet');
    expect(METIER_FAMILLES).toContain("Architecte ou bureau d'études");
    expect(METIER_FAMILLES).toContain('Artisan ou restaurateur');
    expect(METIER_FAMILLES).toContain("Administration ou contrôle de l'État");
    expect(METIER_FAMILLES).toContain('Financement ou conseil');
  });
});
