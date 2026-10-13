import { describe, expect, it } from 'vitest';
import { ETAPES_MIN, GUIDE_IDS, VISITES, etapesJouables, selecteurAncre } from '../guides';

const toutes = GUIDE_IDS.flatMap((id) => VISITES[id].map((e) => ({ id, ...e })));

describe('règles d’écriture des bulles', () => {
  it.each(toutes)('$ancre : titre de 4 mots au plus', ({ titre }) => {
    expect(titre.trim().split(/\s+/).length).toBeLessThanOrEqual(4);
  });

  it.each(toutes)('$ancre : une phrase de 120 caractères au plus', ({ texte }) => {
    expect(texte.length).toBeLessThanOrEqual(120);
    // Une phrase : un seul point final, aucun au milieu.
    expect(texte.replace(/\.$/, '')).not.toMatch(/[.!?]\s/);
  });

  it.each(toutes)('$ancre : ni tiret cadratin ni jargon interne', ({ titre, texte }) => {
    for (const t of [titre, texte]) {
      expect(t).not.toMatch(/[—–]/);
      expect(t.toLowerCase()).not.toMatch(/\bseaux?\b|\bfaits?\b|déterministe/);
    }
  });

  it('4 bulles au plus par écran, et assez pour une visite', () => {
    for (const id of GUIDE_IDS) {
      expect(VISITES[id].length).toBeLessThanOrEqual(4);
      expect(VISITES[id].length).toBeGreaterThanOrEqual(ETAPES_MIN);
    }
  });

  it('identifiants et ancres uniques', () => {
    expect(new Set(GUIDE_IDS).size).toBe(GUIDE_IDS.length);
    const ancres = toutes.map((e) => e.ancre);
    expect(new Set(ancres).size).toBe(ancres.length);
    // Une ancre est préfixée par sa visite : on sait d'un coup d'œil où la poser.
    for (const e of toutes) expect(e.ancre.startsWith(`${e.id}.`)).toBe(true);
  });
});

describe('etapesJouables', () => {
  it('garde les étapes dont l’ancre est visible, dans l’ordre', () => {
    const visibles = new Set(['projet.aides', 'projet.refaire']);
    expect(etapesJouables(VISITES.projet, (a) => visibles.has(a)).map((e) => e.ancre)).toEqual([
      'projet.aides',
      'projet.refaire',
    ]);
  });

  it('rien de visible : aucune étape', () => {
    expect(etapesJouables(VISITES.aide, () => false)).toEqual([]);
  });

  it('le sélecteur vise l’attribut data-guide', () => {
    expect(selecteurAncre('aide.montant')).toBe('[data-guide="aide.montant"]');
  });
});
