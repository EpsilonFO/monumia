import { describe, it, expect } from 'vitest';
import type { AideMatchResult } from '@/types';
import { famillesDisponibles, filtrerParFamille, matchFamille } from '../aide-familles';

/** Aide réduite à ce que les facettes lisent : son id et ses familles. */
function aide(id: string, familles?: string[]): AideMatchResult {
  return { aide: { id, familles } } as unknown as AideMatchResult;
}

const SPECTACLE = aide('a-spectacle', ['spectacles_manifestations']);
const SPECTACLE_BIS = aide('a-spectacle-bis', ['spectacles_manifestations']);
const TOURISME = aide('a-tourisme', ['hebergement_touristique']);
const MIXTE = aide('a-mixte', ['spectacles_manifestations', 'hebergement_touristique']);
const SANS = aide('a-sans');

describe('matchFamille', () => {
  it('accepte tout quand aucune facette n’est choisie', () => {
    for (const m of [SPECTACLE, SANS]) expect(matchFamille(m, null)).toBe(true);
  });

  it('retient une aide qui porte la famille, même parmi plusieurs', () => {
    expect(matchFamille(MIXTE, 'hebergement_touristique')).toBe(true);
    expect(matchFamille(SPECTACLE, 'hebergement_touristique')).toBe(false);
  });

  it('écarte une aide sans famille dès qu’une facette est choisie', () => {
    // Le fail-open du cadrage vaut pour le SERVEUR (`hors_famille`) : une aide
    // sans tag y passe toujours. Une facette cliquée à l'écran est un geste
    // explicite de tri sur ce qu'on a sous les yeux, et rien ne la compte.
    expect(matchFamille(SANS, 'spectacles_manifestations')).toBe(false);
  });
});

describe('filtrerParFamille', () => {
  it('ne touche à rien sans facette', () => {
    const toutes = [SPECTACLE, TOURISME, SANS];
    expect(filtrerParFamille(toutes, null)).toBe(toutes);
  });

  it('ne garde que les aides de la famille', () => {
    expect(
      filtrerParFamille([SPECTACLE, TOURISME, MIXTE, SANS], 'spectacles_manifestations').map(
        (m) => m.aide.id,
      ),
    ).toEqual(['a-spectacle', 'a-mixte']);
  });
});

describe('famillesDisponibles', () => {
  it('compte les familles et trie par compte décroissant', () => {
    expect(famillesDisponibles([SPECTACLE, SPECTACLE_BIS, TOURISME], null)).toEqual([
      { famille: 'spectacles_manifestations', label: 'Spectacles et manifestations', count: 2 },
      { famille: 'hebergement_touristique', label: 'Hébergement touristique', count: 1 },
    ]);
  });

  it('compte une aide dans chacune de ses familles', () => {
    const facettes = famillesDisponibles([MIXTE, TOURISME], null);
    expect(facettes.map((f) => [f.famille, f.count])).toEqual([
      ['hebergement_touristique', 2],
      ['spectacles_manifestations', 1],
    ]);
  });

  it('ne rend rien quand une seule famille ne départage rien', () => {
    expect(famillesDisponibles([SPECTACLE, SPECTACLE_BIS, SANS], null)).toEqual([]);
    expect(famillesDisponibles([SANS], null)).toEqual([]);
  });

  it('garde la facette sélectionnée même vidée par les autres filtres', () => {
    // Sinon la puce qu'on vient de choisir s'évanouirait sous les doigts.
    const facettes = famillesDisponibles([SPECTACLE, TOURISME], 'parcs_jardins_paysages');
    expect(facettes.find((f) => f.famille === 'parcs_jardins_paysages')).toEqual({
      famille: 'parcs_jardins_paysages',
      label: 'Parcs, jardins et paysages',
      count: 0,
    });
  });

  it('range les comptes égaux par libellé', () => {
    const facettes = famillesDisponibles([SPECTACLE, TOURISME], null);
    expect(facettes.map((f) => f.label)).toEqual([
      'Hébergement touristique',
      'Spectacles et manifestations',
    ]);
  });
});
