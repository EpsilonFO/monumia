import { describe, it, expect } from 'vitest';
import { nextUnread } from '../articles';
import type { BlogArticle } from '../articles';

function stub(slug: string): BlogArticle {
  return {
    slug,
    title: slug,
    categorySlug: 'protections-statuts',
    excerpt: '',
    relatedTermKeys: [],
    body: async () => '',
  };
}

describe('nextUnread', () => {
  const list = [stub('a'), stub('b'), stub('c')];

  it('renvoie le premier article quand rien n’est lu', () => {
    expect(nextUnread(list, new Set())?.slug).toBe('a');
  });

  it('renvoie le premier non-lu dans l’ordre', () => {
    expect(nextUnread(list, new Set(['a']))?.slug).toBe('b');
    expect(nextUnread(list, new Set(['a', 'b']))?.slug).toBe('c');
  });

  it('renvoie undefined quand tout est lu', () => {
    expect(nextUnread(list, new Set(['a', 'b', 'c']))).toBeUndefined();
  });

  it('renvoie undefined sur une liste vide', () => {
    expect(nextUnread([], new Set())).toBeUndefined();
  });
});
