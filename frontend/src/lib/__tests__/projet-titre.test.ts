import { describe, expect, it } from 'vitest';
import { projetTitre } from '@/lib/projet-titre';
import type { Projet } from '@/types';

function projet(partial: Partial<Projet>): Projet {
  return {
    id: 'p1',
    monumentId: 'm1',
    userId: 'u1',
    travauxEnvisages: null,
    questionnaire: {},
    createdAt: '',
    updatedAt: '',
    ...partial,
  };
}

describe('projetTitre', () => {
  it('utilise le titre saisi quand il y en a un', () => {
    expect(projetTitre(projet({ titre: 'Chantier du clocher' }))).toBe('Chantier du clocher');
  });

  it('ignore un titre vide ou blanc', () => {
    expect(projetTitre(projet({ titre: '   ', travauxEnvisages: ['toiture'] }))).toBe('Toiture');
  });

  it('décrit le projet par ses travaux, en clair', () => {
    expect(projetTitre(projet({ travauxEnvisages: ['toiture', 'charpente'] }))).toBe(
      'Toiture, Charpente',
    );
  });

  it('abrège au-delà de trois types de travaux', () => {
    expect(
      projetTitre(projet({ travauxEnvisages: ['toiture', 'charpente', 'couverture', 'facade'] })),
    ).toBe('Toiture, Charpente, Couverture +1');
  });

  it('retombe sur la première intention quand les travaux ne sont pas déterminés', () => {
    expect(
      projetTitre(projet({ travauxEnvisages: [], questionnaire: { _raisons: ['fiscalite'] } })),
    ).toBe('Optimiser la fiscalité');
  });

  it('rend toujours quelque chose, même sans aucune information', () => {
    expect(projetTitre(projet({}))).toBe('Projet de travaux');
  });
});
