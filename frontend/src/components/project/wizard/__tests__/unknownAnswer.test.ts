import { describe, expect, it } from 'vitest';
import { isUnknownAnswer } from '../unknownAnswer';

describe('isUnknownAnswer', () => {
  it('détecte par id moteur (skip/unknown/nsp)', () => {
    expect(isUnknownAnswer({ id: 'skip', label: 'Aucune importance' })).toBe(true);
    expect(isUnknownAnswer({ id: 'NSP', label: 'Sans opinion' })).toBe(true);
  });

  it('détecte le drapeau `unknown` de l’ontologie', () => {
    expect(isUnknownAnswer({ id: 'pas_encore_decide', label: 'Pas encore décidé', unknown: true }))
      .toBe(true);
  });

  it('détecte par libellé, accents normalisés', () => {
    expect(isUnknownAnswer({ id: 'a', label: 'Je ne sais pas' })).toBe(true);
    expect(isUnknownAnswer({ id: 'b', label: 'Incertain' })).toBe(true);
    expect(isUnknownAnswer({ id: 'c', label: 'Pas sûr' })).toBe(true);
    expect(isUnknownAnswer({ id: 'd', label: 'Passer cette question' })).toBe(true);
  });

  it('laisse passer les réponses normales', () => {
    expect(isUnknownAnswer({ id: 'd', label: 'Habitation' })).toBe(false);
    expect(isUnknownAnswer({ id: 'e', label: 'Non, aucun' })).toBe(false);
    expect(isUnknownAnswer({ id: 'f', label: 'Usage cultuel' })).toBe(false);
  });

  it('le drapeau explicite `false` prime sur le libellé', () => {
    // Quand le fait DÉCLARE ses réponses, le moteur émet `unknown` dans les
    // deux sens : une réponse de plein droit mal nommée hériterait sinon du
    // « ? », du tri en bas de liste et de l'exclusivité en choix multiple.
    expect(isUnknownAnswer({ id: 'les_deux', label: 'Je ne sais pas trop', unknown: false })).toBe(
      false,
    );
    expect(isUnknownAnswer({ id: 'incertain', label: 'Incertain', unknown: false })).toBe(false);
  });

  it('le repli par libellé reste pour les options fabriquées par le moteur', () => {
    // Pas de drapeau du tout : tranches numériques, couple Oui/Non implicite.
    expect(isUnknownAnswer({ id: 'g', label: 'Je ne sais pas' })).toBe(true);
  });

  it('le pseudo-choix « passer » reste détecté malgré l’absence de drapeau', () => {
    expect(isUnknownAnswer({ id: 'skip', label: 'Passer cette question' })).toBe(true);
  });
});
