import { describe, it, expect } from 'vitest';
import { slugify } from '../slugify';

describe('slugify', () => {
  it('met en minuscules et remplace les espaces', () => {
    expect(slugify('Côté financement')).toBe('cote-financement');
  });
  it('retire les accents et la ponctuation', () => {
    expect(slugify('L’essentiel en bref')).toBe('l-essentiel-en-bref');
  });
  it('coupe les tirets en bord de chaîne', () => {
    expect(slugify('  Un exemple concret ! ')).toBe('un-exemple-concret');
  });
});
