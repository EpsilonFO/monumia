import { slugify } from './slugify';

export interface Heading {
  text: string;
  id: string;
}

/** Titres de niveau 2 du corps Markdown, hors blocs de code et de directives. */
export function extractHeadings(markdown: string): Heading[] {
  const headings: Heading[] = [];
  let inCode = false;
  let inDirective = false;
  for (const line of markdown.split('\n')) {
    const t = line.trim();
    if (t.startsWith('```')) {
      inCode = !inCode;
      continue;
    }
    if (inCode) continue;
    if (t === ':::') {
      inDirective = false;
      continue;
    }
    if (/^:::\S/.test(t)) {
      inDirective = true;
      continue;
    }
    if (inDirective) continue;
    const m = line.match(/^##\s+(.+?)\s*$/);
    if (m) {
      const text = m[1].replace(/[*_`]/g, '').trim();
      headings.push({ text, id: slugify(text) });
    }
  }
  return headings;
}
