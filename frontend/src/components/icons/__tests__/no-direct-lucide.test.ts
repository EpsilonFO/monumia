/// <reference types="node" />
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

// frontend/src
const SRC = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');

/**
 * Plomberie d'interface tolérée : glyphes fonctionnels où une icône « faite
 * main » casserait l'ergonomie (chevrons, croix, coches, spinner, flèches…).
 * Tout autre import de lucide-react dans le métier est interdit — il doit
 * passer par la banque @/components/icons.
 */
const ALLOW = new Set([
  'Loader2',
  'ChevronDown',
  'ChevronUp',
  'ChevronLeft',
  'ChevronRight',
  'ChevronsUpDown',
  'Check',
  'X',
  'Minus',
  'MoreVertical',
  'MoreHorizontal',
  'Menu',
  'EyeOff',
  'ArrowRight',
  'ArrowLeft',
  'ArrowUp',
  'ArrowDown',
  'ArrowUpRight',
]);

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      // Les composants shadcn (components/ui) sont exemptés.
      return entry === 'ui' ? [] : walk(full);
    }
    return /\.(tsx?|jsx?)$/.test(full) ? [full] : [];
  });
}

function offendersOf(file: string): string[] {
  const src = readFileSync(file, 'utf8');
  const offenders: string[] = [];
  const re = /import\s*(?:type\s*)?\{([^}]*)\}\s*from\s*['"]lucide-react['"]/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(src))) {
    const names = m[1]
      .split(',')
      .map((s) => s.trim().split(/\s+as\s+/)[0].trim())
      .filter(Boolean);
    offenders.push(...names.filter((n) => !ALLOW.has(n)));
  }
  return offenders;
}

describe('imports lucide-react', () => {
  it("aucune icône de marque importée directement de lucide-react (hors components/ui)", () => {
    const report: string[] = [];
    for (const file of walk(SRC)) {
      const bad = offendersOf(file);
      if (bad.length) report.push(`${file.replace(SRC, 'src')} → ${bad.join(', ')}`);
    }
    expect(report).toEqual([]);
  });
});
