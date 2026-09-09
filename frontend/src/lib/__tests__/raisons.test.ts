import { describe, it, expect } from 'vitest';
import {
  RAISONS_KEY,
  questionnaireDeCadrage,
  readRaisons,
  sansClesReservees,
  sansEtapeTravaux,
} from '@/constants/raisons';

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

/**
 * L'étape « Les travaux » n'a de sens que pour un chantier. « Faire vivre et
 * ouvrir le lieu » choisi seul la saute ; toute intention de travaux, même
 * mêlée à d'autres sur un projet d'avant le choix exclusif, la garde.
 */
describe('sansEtapeTravaux', () => {
  it('saute l’étape pour « Faire vivre et ouvrir le lieu » seul', () => {
    expect(sansEtapeTravaux(['valorisation_rayonnement'])).toBe(true);
  });

  it('garde l’étape pour un chantier', () => {
    expect(sansEtapeTravaux(['restauration_travaux'])).toBe(false);
    expect(sansEtapeTravaux(['etude_ingenierie'])).toBe(false);
  });

  it('garde l’étape sur un ancien projet multi-intentions', () => {
    expect(sansEtapeTravaux(['valorisation_rayonnement', 'restauration_travaux'])).toBe(false);
  });

  it('garde l’étape sans intention (questionnaire d’avant l’étape)', () => {
    expect(sansEtapeTravaux([])).toBe(false);
  });
});

/**
 * Le cadrage d'un projet (fin de l'étape des travaux) enregistre la finalité
 * SANS attendre la sortie du questionnaire : c'est elle qui écarte du
 * diagnostic les aides d'un autre métier, et la page du projet la relit depuis
 * `projet.questionnaire`. Quitter le wizard en cours de questionnaire ne doit
 * donc plus laisser un projet sans finalité — ni perdre les réponses déjà
 * enregistrées.
 */
describe('questionnaireDeCadrage', () => {
  it('pose la finalité sur un nouveau projet', () => {
    expect(questionnaireDeCadrage(undefined, ['restauration_travaux'])).toEqual({
      [RAISONS_KEY]: ['restauration_travaux'],
    });
  });

  it('garde les réponses aux faits déjà enregistrées', () => {
    expect(
      questionnaireDeCadrage({ etat_travaux: 'non_commences' }, ['etude_ingenierie']),
    ).toEqual({ etat_travaux: 'non_commences', [RAISONS_KEY]: ['etude_ingenierie'] });
  });

  it('remplace l’ancienne finalité, jamais ne l’ajoute', () => {
    expect(
      questionnaireDeCadrage(
        { [RAISONS_KEY]: ['valorisation_rayonnement'], fait: 'oui' },
        ['restauration_travaux'],
      ),
    ).toEqual({ fait: 'oui', [RAISONS_KEY]: ['restauration_travaux'] });
  });

  it('ne mute pas le questionnaire enregistré', () => {
    const source = { [RAISONS_KEY]: ['valorisation_rayonnement'], fait: 'oui' };
    questionnaireDeCadrage(source, ['restauration_travaux']);
    expect(source).toEqual({ [RAISONS_KEY]: ['valorisation_rayonnement'], fait: 'oui' });
  });

  it('est relu par readRaisons', () => {
    expect(readRaisons(questionnaireDeCadrage({}, ['valorisation_rayonnement']))).toEqual([
      'valorisation_rayonnement',
    ]);
  });
});
