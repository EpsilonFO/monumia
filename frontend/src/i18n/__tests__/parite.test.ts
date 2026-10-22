import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { NAMESPACES } from '../ressources';

// Toutes les langues doivent porter exactement les clés du français, avec les
// mêmes variables et les mêmes balises : une clé manquante s'afficherait en
// français au milieu d'un écran anglais, une variable oubliée laisserait un
// « {{nom}} » à l'écran, une balise perdue casserait un lien <Trans>.

const DOSSIER = path.resolve(__dirname, '../locales');
const LANGUES = readdirSync(DOSSIER).filter((d) => d !== 'fr');
const SUFFIXE_PLURIEL = /_(zero|one|two|few|many|other)$/;

type Arbre = { [cle: string]: Arbre | string | Arbre[] | string[] };

function lire(langue: string, ns: string): Arbre {
  return JSON.parse(readFileSync(path.join(DOSSIER, langue, `${ns}.json`), 'utf8')) as Arbre;
}

/** Feuilles à plat : chemin → texte. Les tableaux comptent comme des feuilles indexées. */
function aplatir(noeud: unknown, prefixe = '', sortie = new Map<string, string>()) {
  if (typeof noeud === 'string') {
    sortie.set(prefixe, noeud);
  } else if (Array.isArray(noeud)) {
    noeud.forEach((v, i) => aplatir(v, `${prefixe}[${i}]`, sortie));
  } else if (noeud && typeof noeud === 'object') {
    for (const [cle, v] of Object.entries(noeud)) {
      aplatir(v, prefixe ? `${prefixe}.${cle}` : cle, sortie);
    }
  }
  return sortie;
}

/** Les formes plurielles diffèrent d'une langue à l'autre : on compare la clé de base. */
function bases(feuilles: Map<string, string>): Set<string> {
  return new Set([...feuilles.keys()].map((k) => k.replace(SUFFIXE_PLURIEL, '')));
}

function variables(texte: string): string[] {
  return [...texte.matchAll(/\{\{\s*([\w.]+)[^}]*\}\}/g)].map((m) => m[1]).sort();
}

function balises(texte: string): string[] {
  return [...texte.matchAll(/<\/?([\w-]+)\s*\/?>/g)].map((m) => m[0].replace(/\s/g, '')).sort();
}

describe('fichiers de traduction', () => {
  it('chaque langue a un fichier par namespace déclaré', () => {
    for (const langue of ['fr', ...LANGUES]) {
      const fichiers = readdirSync(path.join(DOSSIER, langue))
        .filter((f) => f.endsWith('.json'))
        .map((f) => f.replace(/\.json$/, ''))
        .sort();
      expect(fichiers, langue).toEqual([...NAMESPACES].sort());
    }
  });

  it("aucun texte français n'est vide", () => {
    for (const ns of NAMESPACES) {
      for (const [cle, texte] of aplatir(lire('fr', ns))) {
        expect(texte.trim(), `fr/${ns}:${cle}`).not.toBe('');
      }
    }
  });

  for (const langue of LANGUES) {
    describe(langue, () => {
      for (const ns of NAMESPACES) {
        it(`${ns} : mêmes clés que le français`, () => {
          const fr = bases(aplatir(lire('fr', ns)));
          const autre = bases(aplatir(lire(langue, ns)));
          expect([...fr].filter((k) => !autre.has(k)), 'manquantes').toEqual([]);
          expect([...autre].filter((k) => !fr.has(k)), 'en trop').toEqual([]);
        });

        it(`${ns} : mêmes variables et balises, aucun texte vide`, () => {
          const fr = aplatir(lire('fr', ns));
          const autre = aplatir(lire(langue, ns));
          // Les formes plurielles se comparent à la forme « other » du français.
          const reference = (cle: string) =>
            fr.get(cle) ?? fr.get(cle.replace(SUFFIXE_PLURIEL, '_other')) ?? fr.get(cle.replace(SUFFIXE_PLURIEL, ''));
          for (const [cle, texte] of autre) {
            const source = reference(cle);
            if (source === undefined) continue;
            expect(texte.trim(), `${langue}/${ns}:${cle} vide`).not.toBe('');
            // `count` peut manquer d'une forme singulière (« One file » / « 1 fichier »).
            const sansCount = (v: string[]) => v.filter((x) => x !== 'count');
            expect(sansCount(variables(texte)), `${langue}/${ns}:${cle}`).toEqual(
              sansCount(variables(source)),
            );
            expect(balises(texte), `${langue}/${ns}:${cle}`).toEqual(balises(source));
          }
        });
      }
    });
  }
});
