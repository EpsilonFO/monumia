import { describe, it, expect } from 'vitest';
import {
  parseReadSlugs,
  serializeReadSlugs,
  withRead,
  countRead,
} from '../readState';

describe('readState', () => {
  it('parse un tableau JSON valide', () => {
    expect(parseReadSlugs('["a","b"]')).toEqual(new Set(['a', 'b']));
  });

  it('renvoie un ensemble vide si null', () => {
    expect(parseReadSlugs(null).size).toBe(0);
  });

  it('renvoie un ensemble vide si JSON invalide ou non-tableau', () => {
    expect(parseReadSlugs('pas du json').size).toBe(0);
    expect(parseReadSlugs('{"a":1}').size).toBe(0);
  });

  it('ignore les entrées non-chaîne', () => {
    expect(parseReadSlugs('["a",1,null,"b"]')).toEqual(new Set(['a', 'b']));
  });

  it('withRead ajoute sans muter et dédoublonne', () => {
    const base = new Set(['a']);
    const next = withRead(base, 'b');
    expect(next).toEqual(new Set(['a', 'b']));
    expect(base).toEqual(new Set(['a']));
    expect(withRead(next, 'b')).toEqual(new Set(['a', 'b']));
  });

  it('serialize produit un JSON reparsables', () => {
    const set = new Set(['x', 'y']);
    expect(parseReadSlugs(serializeReadSlugs(set))).toEqual(set);
  });

  it('countRead compte les slugs lus d’une liste', () => {
    expect(countRead(new Set(['a', 'c']), ['a', 'b', 'c'])).toBe(2);
    expect(countRead(new Set(), ['a', 'b'])).toBe(0);
  });
});
