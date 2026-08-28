import { describe, it, expect } from 'vitest';
import { enjeuLabel } from '../aides-enjeu';

/** `formatPercentage` colle le % à son nombre par une espace insécable. */
const pct = (n: number) => `${n}\u00A0%`;

describe('enjeuLabel', () => {
  it('annonce un maximum, pas une prevision', () => {
    const { value } = enjeuLabel({ montantPotentiel: 125000, tauxTravauxMax: 0 });
    expect(value).toContain('Jusqu’à');
    expect(value).toContain('125');
  });

  it('juxtapose les deux registres de chiffrage', () => {
    const { value, sub } = enjeuLabel({ montantPotentiel: 125000, tauxTravauxMax: 60 });
    expect(value).toContain('Jusqu’à');
    expect(sub).toBe(`et / ou ${pct(60)} des travaux`);
  });

  it('porte la case sur le seul taux quand aucune aide ne plafonne en euros', () => {
    const { value, sub } = enjeuLabel({ montantPotentiel: 0, tauxTravauxMax: 80 });
    expect(value).toBe(`Jusqu’à ${pct(80)} des travaux`);
    expect(sub).toBeUndefined();
  });

  it('reste muette sans chiffrage', () => {
    expect(enjeuLabel({ montantPotentiel: 0, tauxTravauxMax: 0 })).toEqual({ value: '—' });
  });
});
