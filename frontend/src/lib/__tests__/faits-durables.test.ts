import { describe, it, expect } from 'vitest';
import { clesApportees, fusionnerFaitsDurables } from '../faits-durables';

/**
 * La reprise des faits durables est une COMMODITÉ, pas une autorité : ce qui a
 * été répondu sur CE projet gagne toujours. Inverser les deux termes ne casse
 * aucun écran — ça écrase juste des réponses sans le dire —, d'où ces tests.
 */
describe('fusionnerFaitsDurables', () => {
  it('apporte les réponses absentes du projet', () => {
    expect(fusionnerFaitsDurables({ edifice_cultuel: 'oui' }, { etat_travaux: 'aucun' })).toEqual({
      edifice_cultuel: 'oui',
      etat_travaux: 'aucun',
    });
  });

  it('ne remplace jamais une réponse donnée sur ce projet', () => {
    expect(
      fusionnerFaitsDurables({ edifice_cultuel: 'oui' }, { edifice_cultuel: 'non' }),
    ).toEqual({ edifice_cultuel: 'non' });
  });

  it('ne mute aucun des deux dictionnaires', () => {
    const durables = { edifice_cultuel: 'oui' };
    const propres = { etat_travaux: 'aucun' };
    fusionnerFaitsDurables(durables, propres);
    expect(durables).toEqual({ edifice_cultuel: 'oui' });
    expect(propres).toEqual({ etat_travaux: 'aucun' });
  });

  it('accepte les deux côtés vides', () => {
    expect(fusionnerFaitsDurables({}, {})).toEqual({});
  });
});

describe('clesApportees', () => {
  it('ne retient que ce que la reprise APPORTE', () => {
    // « 12 réponses reprises » là où l'utilisateur n'en reconnaît que trois se
    // lit comme une erreur — et le bandeau NOMME chacune, donc une clé de trop
    // affiche une question qu'on n'a pas reprise.
    expect(clesApportees({ a: 'oui', b: 'non', c: 'oui' }, { a: 'non' })).toEqual(['b', 'c']);
  });

  it('ne retient rien quand le projet portait déjà tout', () => {
    expect(clesApportees({ a: 'oui' }, { a: 'non' })).toEqual([]);
    expect(clesApportees({}, { a: 'oui' })).toEqual([]);
  });
});
