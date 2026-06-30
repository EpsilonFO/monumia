import { describe, it, expect } from 'vitest';
import { extractHeadings } from '../extractHeadings';

const md = [
  'Une accroche.',
  '',
  '## L’essentiel en bref',
  'texte',
  '',
  ':::comparatif',
  '### Bien inscrit',
  '- point',
  ':::',
  '',
  '## Un exemple concret',
  '',
  '```',
  '## pas un titre',
  '```',
].join('\n');

describe('extractHeadings', () => {
  it('ne retient que les titres de niveau 2 hors directives et code', () => {
    expect(extractHeadings(md)).toEqual([
      { text: 'L’essentiel en bref', id: 'l-essentiel-en-bref' },
      { text: 'Un exemple concret', id: 'un-exemple-concret' },
    ]);
  });
});
