import { describe, expect, it } from 'vitest';
import {
  computeEliminatedAideIds,
  countLiveAides,
  isQuestionPartagee,
  isQuestionServingLiveAide,
  isVisible,
  partitionnerQuestions,
  selectedIds,
} from '../qcm';
import type { QcmQuestion } from '@/types';

/** Question du moteur, réduite à ce que la fonction lit. */
function question(over: Partial<QcmQuestion> = {}): QcmQuestion {
  return {
    id: 'statut_juridique_porteur',
    question: 'Quelles entités pourraient déposer ?',
    multiple: true,
    options: [
      { id: 'prive_personne_physique', label: 'Particulier' },
      { id: 'association', label: 'Association' },
      { id: 'public_commune', label: 'Commune' },
      { id: 'pas_encore_decide', label: 'Pas encore décidé', unknown: true },
    ],
    aideIds: ['aide-asso', 'aide-commune', 'aide-tous'],
    eliminatingOptionIds: [],
    eliminationsParOption: {
      prive_personne_physique: ['aide-asso', 'aide-commune'],
      association: ['aide-commune'],
      public_commune: ['aide-asso'],
    },
    ...over,
  };
}

describe('computeEliminatedAideIds', () => {
  it('choix simple : la carte de la réponse s’applique', () => {
    const q = question({ multiple: false });
    expect(computeEliminatedAideIds({ [q.id]: 'prive_personne_physique' }, [q]).sort()).toEqual([
      'aide-asso',
      'aide-commune',
    ]);
  });

  it('question passée ou sans réponse : rien d’écarté', () => {
    const q = question({ multiple: false });
    expect(computeEliminatedAideIds({}, [q])).toEqual([]);
    expect(computeEliminatedAideIds({ [q.id]: 'skip' }, [q])).toEqual([]);
  });

  it('choix multiple : seules les aides écartées par TOUTES les cases tombent', () => {
    const q = question();
    // Particulier écarte {asso, commune}, association écarte {commune} →
    // l'aide réservée aux associations reste, on déposera sous l'association.
    expect(
      computeEliminatedAideIds({ [q.id]: ['prive_personne_physique', 'association'] }, [q]),
    ).toEqual(['aide-commune']);
  });

  it('choix multiple : une case sans élimination libère tout', () => {
    const q = question();
    expect(
      computeEliminatedAideIds({ [q.id]: ['prive_personne_physique', 'inconnue'] }, [q]),
    ).toEqual([]);
  });

  it('« pas encore décidé » n’écarte rien, même coché avec une autre case', () => {
    const q = question();
    expect(computeEliminatedAideIds({ [q.id]: ['pas_encore_decide'] }, [q])).toEqual([]);
    expect(
      computeEliminatedAideIds({ [q.id]: ['pas_encore_decide', 'association'] }, [q]),
    ).toEqual(['aide-commune']);
  });

  it('format grossier (sans eliminationsParOption) : toutes les aides de la question tombent', () => {
    const q = question({
      multiple: false,
      eliminationsParOption: undefined,
      eliminatingOptionIds: ['prive_personne_physique'],
    });
    expect(computeEliminatedAideIds({ [q.id]: 'prive_personne_physique' }, [q]).sort()).toEqual([
      'aide-asso',
      'aide-commune',
      'aide-tous',
    ]);
  });
});

describe('isQuestionServingLiveAide', () => {
  const q = question({ id: 'duree_location', aideIds: ['denormandie', 'malraux'] });

  it('toutes ses aides écartées : la question ne sert plus à rien', () => {
    expect(isQuestionServingLiveAide(q, ['denormandie', 'malraux'])).toBe(false);
  });

  it('une seule aide encore en lice : la question reste posée', () => {
    expect(isQuestionServingLiveAide(q, ['denormandie'])).toBe(true);
    expect(isQuestionServingLiveAide(q, [])).toBe(true);
  });

  it('sans aideIds exploitable : fail-open, la question reste posée', () => {
    expect(isQuestionServingLiveAide(question({ aideIds: [] }), ['denormandie'])).toBe(true);
    expect(
      isQuestionServingLiveAide(question({ aideIds: undefined as unknown as string[] }), [
        'denormandie',
      ]),
    ).toBe(true);
  });

  it('une réponse « je ne sais pas » n’écarte rien, donc ne masque rien', () => {
    const porteuse = question();
    const eliminated = computeEliminatedAideIds({ [porteuse.id]: ['pas_encore_decide'] }, [
      porteuse,
    ]);
    expect(isQuestionServingLiveAide(question({ aideIds: ['aide-asso'] }), eliminated)).toBe(true);
  });
});

describe('selectedIds', () => {
  const q = question();
  it('rend une liste, que la réponse soit simple ou multiple', () => {
    expect(selectedIds(q, { [q.id]: 'association' })).toEqual(['association']);
    expect(selectedIds(q, { [q.id]: ['association', 'public_commune'] })).toEqual([
      'association',
      'public_commune',
    ]);
    expect(selectedIds(q, {})).toEqual([]);
  });
});

describe('isVisible', () => {
  const dependante = question({
    id: 'age_orgue_ans',
    dependsOn: { questionId: 'possede_orgue_a_tuyaux', showForOptionIds: ['oui'] },
  });

  it('sans dependsOn : toujours visible', () => {
    expect(isVisible(question(), {})).toBe(true);
  });

  it('fail-closed : la porteuse sans réponse ou passée laisse la question posée', () => {
    expect(isVisible(dependante, {})).toBe(true);
    expect(isVisible(dependante, { possede_orgue_a_tuyaux: 'skip' })).toBe(true);
  });

  it('la réponse de la porteuse décide', () => {
    expect(isVisible(dependante, { possede_orgue_a_tuyaux: 'oui' })).toBe(true);
    expect(isVisible(dependante, { possede_orgue_a_tuyaux: 'non' })).toBe(false);
    // Porteuse à choix multiple : une seule case pertinente suffit.
    expect(isVisible(dependante, { possede_orgue_a_tuyaux: ['non', 'oui'] })).toBe(true);
  });
});

describe('countLiveAides / isQuestionPartagee', () => {
  it('ne compte que les aides que les réponses n’ont pas écartées', () => {
    const q = question();
    expect(countLiveAides(q, new Set())).toBe(3);
    expect(countLiveAides(q, new Set(['aide-asso']))).toBe(2);
    expect(countLiveAides(q, new Set(['aide-asso', 'aide-commune', 'aide-tous']))).toBe(0);
  });

  it('deux aides dont une éliminée : la question quitte le tronc', () => {
    const q = question({ aideIds: ['aide-asso', 'aide-commune'] });
    expect(isQuestionPartagee(q, new Set())).toBe(true);
    expect(isQuestionPartagee(q, new Set(['aide-commune']))).toBe(false);
  });

  it('le seuil est paramétrable', () => {
    expect(isQuestionPartagee(question(), new Set(), 3)).toBe(true);
    expect(isQuestionPartagee(question(), new Set(), 4)).toBe(false);
  });

  it('fail-open : sans aideIds exploitable, la question reste dans le tronc', () => {
    expect(isQuestionPartagee(question({ aideIds: [] }), new Set())).toBe(true);
  });
});

describe('partitionnerQuestions', () => {
  /** Question minimale, sans élimination, avec les aides qu'on lui donne. */
  const q2 = (id: string, aideIds: string[], over: Partial<QcmQuestion> = {}) =>
    question({
      id,
      multiple: false,
      aideIds,
      eliminationsParOption: {},
      options: [
        { id: 'oui', label: 'Oui' },
        { id: 'non', label: 'Non' },
      ],
      ...over,
    });

  it('sépare les questions partagées de celles propres à une aide', () => {
    const partagee = q2('etat_travaux', ['a', 'b', 'c']);
    const propre = q2('age_orgue_ans', ['a']);
    const { tronc, propres } = partitionnerQuestions([partagee, propre], {});
    expect(tronc.map((q) => q.id)).toEqual(['etat_travaux']);
    expect(propres.map((q) => q.id)).toEqual(['age_orgue_ans']);
  });

  it('une question dont toutes les aides sont écartées disparaît des deux listes', () => {
    const q = question({ multiple: false });
    // « Particulier » écarte asso et commune ; « aide-tous » reste vivante, donc
    // une question qui ne servait que ces deux-là n'a plus d'objet.
    const morte = q2('duree_engagement_location', ['aide-asso', 'aide-commune']);
    const { tronc, propres } = partitionnerQuestions(
      [q, morte],
      { [q.id]: 'prive_personne_physique' },
    );
    expect([...tronc, ...propres].map((qq) => qq.id)).not.toContain('duree_engagement_location');
  });

  it('une question passée reste utile : « skip » n’écarte rien', () => {
    const partagee = q2('etat_travaux', ['a', 'b']);
    const { tronc } = partitionnerQuestions([partagee], { etat_travaux: 'skip' });
    expect(tronc.map((q) => q.id)).toEqual(['etat_travaux']);
  });

  it('la porteuse mono-aide suit sa dépendante dans le tronc', () => {
    // Cas de la déduction (aideIds indépendants) : la porteuse ne sert qu'une
    // aide, mais sans elle la question branchée ne serait jamais posée.
    const porteuse = q2('ouverture_public', ['a']);
    const dependante = q2('jours_ouverture_public_par_an', ['b', 'c'], {
      dependsOn: { questionId: 'ouverture_public', showForOptionIds: ['oui'] },
    });
    const { tronc, propres } = partitionnerQuestions([porteuse, dependante], {});
    expect(tronc.map((q) => q.id)).toEqual([
      'ouverture_public',
      'jours_ouverture_public_par_an',
    ]);
    expect(propres).toEqual([]);
  });

  it('une dépendante partagée n’est jamais évincée à cause de sa porteuse', () => {
    const porteuse = q2('ouverture_public', ['a']);
    const dependante = q2('jours_ouverture_public_par_an', ['b', 'c'], {
      dependsOn: { questionId: 'ouverture_public', showForOptionIds: ['oui'] },
    });
    const { tronc } = partitionnerQuestions([porteuse, dependante], {});
    expect(tronc.map((q) => q.id)).toContain('jours_ouverture_public_par_an');
  });

  it('une dépendante MONO-aide ne tire pas sa porteuse dans le tronc', () => {
    const porteuse = q2('ouverture_public', ['a']);
    const dependante = q2('jours_ouverture_public_par_an', ['b'], {
      dependsOn: { questionId: 'ouverture_public', showForOptionIds: ['oui'] },
    });
    const { tronc, propres } = partitionnerQuestions([porteuse, dependante], {});
    expect(tronc).toEqual([]);
    expect(propres.map((q) => q.id)).toEqual([
      'ouverture_public',
      'jours_ouverture_public_par_an',
    ]);
  });
});
