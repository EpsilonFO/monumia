import { describe, expect, it } from 'vitest';
import { aideGridSpans } from '../aide-grid';

// La grille des aides fait 6 colonnes en lg : span 2 = rangée de trois,
// span 3 = rangée de deux. Chaque rangée doit toujours être pleine.
const lgSpan = (cls: string) => (cls.includes('lg:col-span-3') ? 3 : 2);
const smSpan = (cls: string) => (cls.includes('sm:col-span-2') ? 2 : 1);

describe('aideGridSpans', () => {
  it('retourne une classe par carte', () => {
    for (let n = 2; n <= 12; n++) {
      expect(aideGridSpans(n)).toHaveLength(n);
    }
  });

  it('2 cartes → un duo pleine largeur', () => {
    expect(aideGridSpans(2).map(lgSpan)).toEqual([3, 3]);
  });

  it('3 cartes → un trio', () => {
    expect(aideGridSpans(3).map(lgSpan)).toEqual([2, 2, 2]);
  });

  it('4 cartes → deux duos (2×2), pas de rangée orpheline', () => {
    expect(aideGridSpans(4).map(lgSpan)).toEqual([3, 3, 3, 3]);
  });

  it('5 cartes → un trio puis un duo', () => {
    expect(aideGridSpans(5).map(lgSpan)).toEqual([2, 2, 2, 3, 3]);
  });

  it('remplit toujours chaque rangée lg (aucun vide), pour tout n', () => {
    for (let n = 2; n <= 30; n++) {
      const spans = aideGridSpans(n).map(lgSpan);
      let row = 0;
      for (const s of spans) {
        row += s;
        expect(row).toBeLessThanOrEqual(6);
        if (row === 6) row = 0;
      }
      expect(row).toBe(0); // la dernière rangée est pleine elle aussi
    }
  });

  it('remplit toujours chaque rangée sm (2 colonnes), pour tout n', () => {
    for (let n = 2; n <= 30; n++) {
      const spans = aideGridSpans(n).map(smSpan);
      let row = 0;
      for (const s of spans) {
        row += s;
        expect(row).toBeLessThanOrEqual(2);
        if (row === 2) row = 0;
      }
      expect(row).toBe(0);
    }
  });
});
