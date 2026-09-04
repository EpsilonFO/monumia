import { describe, it, expect } from 'vitest';
import { RAISONS_KEY, readRaisons, sansClesReservees } from '@/constants/raisons';

/**
 * Un `questionnaire` persisté mêle deux natures : les réponses aux faits, et
 * les clés RÉSERVÉES préfixées « _ » (les intentions de projet). `readRaisons`
 * et `sansClesReservees` sont les deux moitiés de cette décomposition, et
 * « Refaire seulement les questions passées » repose entièrement dessus : les
 * réponses reprises alimentent l'état du questionnaire, les intentions sont
 * recomposées à l'enregistrement.
 */
describe('sansClesReservees', () => {
  it('garde les réponses aux faits', () => {
    expect(
      sansClesReservees({ etat_travaux: 'non_commences', proprietaire_type: 'prive' }),
    ).toEqual({ etat_travaux: 'non_commences', proprietaire_type: 'prive' });
  });

  it('retire les intentions', () => {
    expect(
      sansClesReservees({ [RAISONS_KEY]: ['restauration_travaux'], etat_travaux: 'acheves' }),
    ).toEqual({ etat_travaux: 'acheves' });
  });

  it('retire toute clé réservée, pas seulement celle qu’on connaît', () => {
    // Le préfixe est un espace de noms, pas une liste : une clé réservée
    // ajoutée plus tard doit tomber sans qu'on y revienne.
    expect(sansClesReservees({ _futur: 'x', fait: 'oui' })).toEqual({ fait: 'oui' });
  });

  it('préserve les réponses à choix multiple', () => {
    expect(sansClesReservees({ statut: ['prive', 'association'] })).toEqual({
      statut: ['prive', 'association'],
    });
  });

  it('tolère l’absence de questionnaire', () => {
    expect(sansClesReservees(undefined)).toEqual({});
    expect(sansClesReservees({})).toEqual({});
  });

  it('ne mute pas son entrée', () => {
    const source = { [RAISONS_KEY]: ['fiscalite'], fait: 'oui' };
    sansClesReservees(source);
    expect(source).toEqual({ [RAISONS_KEY]: ['fiscalite'], fait: 'oui' });
  });

  it('est complémentaire de readRaisons', () => {
    const questionnaire = {
      [RAISONS_KEY]: ['restauration_travaux'],
      etat_travaux: 'non_commences',
    };
    expect(readRaisons(questionnaire)).toEqual(['restauration_travaux']);
    expect(Object.keys(sansClesReservees(questionnaire))).toEqual(['etat_travaux']);
  });
});
