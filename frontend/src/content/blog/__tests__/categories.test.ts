import { describe, it, expect } from 'vitest';
import { BLOG_CATEGORIES, getCategory, categoryTone } from '../categories';

describe('catégories blog', () => {
  it('expose 4 catégories avec tone 1..4', () => {
    expect(BLOG_CATEGORIES.map((c) => c.tone)).toEqual([1, 2, 3, 4]);
  });

  it('chaque catégorie a une icône, un stepLabel et une description', () => {
    for (const c of BLOG_CATEGORIES) {
      expect(typeof c.icon).toBe('function');
      expect(c.stepLabel.length).toBeGreaterThan(0);
      expect(c.description.length).toBeGreaterThan(0);
    }
  });

  it('categoryTone mappe tone → tokens cat-N', () => {
    const cat = getCategory('protections-statuts')!;
    expect(categoryTone(cat)).toEqual({ fg: 'var(--cat-1)', soft: 'var(--cat-1-soft)' });
  });
});
