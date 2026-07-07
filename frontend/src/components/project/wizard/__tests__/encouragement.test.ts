import { describe, expect, it } from 'vitest';
import { encouragement } from '../WizardRail';

describe('encouragement', () => {
  it('étape monument', () => {
    expect(encouragement(1, null)).toBe('C’est parti !');
  });

  it('début de questionnaire', () => {
    expect(encouragement(2, { index: 0, total: 12 })).toBe('C’est parti !');
  });

  it('au quart : sur la bonne voie', () => {
    expect(encouragement(2, { index: 3, total: 12 })).toBe('Vous êtes sur la bonne voie.');
  });

  it('à mi-parcours : compte les questions restantes', () => {
    expect(encouragement(2, { index: 6, total: 12 })).toBe('Plus que 6 questions !');
    expect(encouragement(2, { index: 2, total: 3 })).toBe('Plus qu’une question !');
  });

  it('aux trois quarts : presque fini', () => {
    expect(encouragement(2, { index: 9, total: 12 })).toBe('Presque fini !');
  });

  it('diagnostic en cours', () => {
    expect(encouragement(3, null)).toBe('Votre diagnostic arrive…');
  });

  it('écran de fin', () => {
    expect(encouragement(2, { index: 12, total: 12 })).toBe('C’est tout !');
  });
});
