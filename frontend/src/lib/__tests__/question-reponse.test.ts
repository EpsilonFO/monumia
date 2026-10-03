import { describe, expect, it } from 'vitest';
import {
  displayOrder,
  reponsesAffichees,
  reponsesChoisies,
  toggleMulti,
} from '../question-reponse';
import type { QcmQuestion } from '@/types';

function question(over: Partial<QcmQuestion> = {}): QcmQuestion {
  return {
    id: 'statut_juridique_porteur',
    question: 'Qui pourrait déposer ?',
    multiple: true,
    options: [
      { id: 'prive_personne_physique', label: 'Particulier' },
      { id: 'pas_encore_decide', label: 'Pas encore décidé', unknown: true },
      { id: 'association', label: 'Association' },
      { id: 'public_commune', label: 'Commune' },
    ],
    aideIds: ['a', 'b'],
    eliminatingOptionIds: [],
    ...over,
  };
}

const opt = (q: QcmQuestion, id: string) => q.options.find((o) => o.id === id)!;

describe('displayOrder', () => {
  it('les vraies réponses d’abord, les échappatoires en bas', () => {
    expect(displayOrder(question()).map((o) => o.id)).toEqual([
      'prive_personne_physique',
      'association',
      'public_commune',
      'pas_encore_decide',
    ]);
  });

  it('reconnaît une échappatoire au libellé quand le moteur ne déclare rien', () => {
    const q = question({
      options: [
        { id: 'a', label: 'Oui' },
        { id: 'b', label: 'Je ne sais pas' },
      ],
    });
    expect(displayOrder(q).map((o) => o.id)).toEqual(['a', 'b']);
  });
});

describe('toggleMulti', () => {
  const q = question();

  it('coche et décoche', () => {
    expect(toggleMulti(q, [], opt(q, 'association'))).toEqual(['association']);
    expect(toggleMulti(q, ['association'], opt(q, 'association'))).toEqual([]);
  });

  it('trie dans l’ordre du moteur, pas dans celui des clics', () => {
    expect(toggleMulti(q, ['public_commune'], opt(q, 'prive_personne_physique'))).toEqual([
      'prive_personne_physique',
      'public_commune',
    ]);
  });

  it('« je ne sais pas » est exclusif des autres réponses', () => {
    expect(
      toggleMulti(q, ['association', 'public_commune'], opt(q, 'pas_encore_decide')),
    ).toEqual(['pas_encore_decide']);
  });

  it('cocher une vraie réponse chasse le « je ne sais pas »', () => {
    expect(toggleMulti(q, ['pas_encore_decide'], opt(q, 'association'))).toEqual(['association']);
  });

  it('ne mute pas la sélection reçue', () => {
    const current = ['public_commune'];
    toggleMulti(q, current, opt(q, 'prive_personne_physique'));
    expect(current).toEqual(['public_commune']);
  });
});

describe('reponsesAffichees', () => {
  it('retire le pseudo-choix « passer » du moteur, garde les « je ne sais pas » déclarés', () => {
    const q = question({
      multiple: false,
      options: [
        { id: 'a', label: 'Oui' },
        { id: 'nsp', label: 'Pas encore décidé', unknown: true },
        { id: 'skip', label: 'Passer cette question' },
      ],
    });
    expect(reponsesAffichees(q).map((o) => o.id)).toEqual(['a', 'nsp']);
  });
});

describe('reponsesChoisies', () => {
  it('ignore une réponse « skip » déjà enregistrée', () => {
    expect(reponsesChoisies('skip')).toEqual([]);
    expect(reponsesChoisies(undefined)).toEqual([]);
    expect(reponsesChoisies('a')).toEqual(['a']);
    expect(reponsesChoisies(['a', 'b'])).toEqual(['a', 'b']);
  });
});
