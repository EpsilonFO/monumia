import { createElement, type ComponentType } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import * as Icons from '../index';

// Toutes les icônes exportées (fonctions dont le nom commence par « Icon »).
const entries = Object.entries(Icons).filter(
  ([name, value]) => name.startsWith('Icon') && typeof value === 'function',
) as [string, ComponentType<{ size?: number }>][];

describe("banque d'icônes", () => {
  it('expose au moins 45 icônes', () => {
    expect(entries.length).toBeGreaterThanOrEqual(45);
  });

  it.each(entries)('%s rend un <svg> currentColor', (_name, Comp) => {
    const html = renderToStaticMarkup(createElement(Comp));
    expect(html).toContain('<svg');
    expect(html).toContain('viewBox');
    expect(/(?:fill|stroke)="currentColor"/.test(html)).toBe(true);
  });

  it('respecte la prop size', () => {
    const html = renderToStaticMarkup(createElement(Icons.IconAide, { size: 48 }));
    expect(html).toContain('width="48"');
    expect(html).toContain('height="48"');
  });
});
