import { describe, expect, it } from 'vitest';
import {
  canoniser,
  filtrerConditions,
  inventaireSurcharges,
  phraseLisible,
  predicatUtile,
} from '@/lib/admin-predicats';
import type { AdminCondition, ConditionOrpheline, EtatPredicat } from '@/types/admin.types';

const REPONSES = [
  { id: 'association', label: 'Association' },
  { id: 'commune', label: 'Commune' },
  { id: 'prive', label: 'Particulier' },
];

function condition(over: Partial<AdminCondition> = {}): AdminCondition {
  return {
    aideSlug: 'drac-mh-classes',
    aideNom: 'Subvention DRAC — monument classé',
    conditionId: 'porteur-eligible',
    text: 'Le porteur doit être une association ou une commune.',
    factKey: 'statut_porteur',
    question: 'Quel est le statut du porteur ?',
    reponses: REPONSES,
    operateur: 'in',
    valeurs: ['association', 'commune'],
    engineReady: true,
    retiree: false,
    derogationPossible: false,
    surcharge: null,
    ...over,
  };
}

function surcharge(etat: EtatPredicat) {
  return {
    etat,
    detail: null,
    appliquee: etat === 'active' || etat === 'a_revoir',
    predicate: { in: ['association'] },
    predicateOrigine: { eq: 'association' },
    predicateYaml: { eq: 'association' },
    conditionText: 'Le porteur doit être une association ou une commune.',
    conditionTextActuel: 'Le porteur doit être une association ou une commune.',
    factKey: 'statut_porteur',
    motif: null,
  };
}

describe('canoniser', () => {
  it('ramène un `in` à une seule valeur vers `eq`', () => {
    // 28 des 412 gates du corpus. Sans ça, recomposer le prédicat d'origine
    // depuis le menu écrirait une surcharge qui ne change rien.
    expect(canoniser('in', ['commune'])).toEqual({ operateur: 'eq', valeurs: ['commune'] });
  });

  it('ramène un `not_in` à une seule valeur vers `neq`', () => {
    expect(canoniser('not_in', ['commune'])).toEqual({ operateur: 'neq', valeurs: ['commune'] });
  });

  it('promeut un `eq` à plusieurs valeurs en `in`', () => {
    expect(canoniser('eq', ['commune', 'association'])).toEqual({
      operateur: 'in',
      valeurs: ['association', 'commune'],
    });
  });

  it('trie et dédoublonne', () => {
    expect(canoniser('in', ['prive', 'association', 'prive']).valeurs).toEqual([
      'association',
      'prive',
    ]);
  });
});

describe('predicatUtile', () => {
  it('rend null quand le brouillon revient au prédicat servi', () => {
    expect(
      predicatUtile({ operateur: 'in', valeurs: ['association', 'commune'] }, { operateur: 'in', valeurs: ['commune', 'association'] }),
    ).toBeNull();
  });

  it('rend null malgré une forme différente mais canoniquement égale', () => {
    // L'administrateur recompose `eq: commune` depuis un menu qui dit « est ».
    expect(
      predicatUtile({ operateur: 'in', valeurs: ['commune'] }, { operateur: 'eq', valeurs: ['commune'] }),
    ).toBeNull();
  });

  it('rend le prédicat canonisé quand il diffère', () => {
    expect(
      predicatUtile({ operateur: 'eq', valeurs: ['commune'] }, { operateur: 'in', valeurs: ['commune', 'association'] }),
    ).toEqual({ operateur: 'in', valeurs: ['association', 'commune'] });
  });

  it('rend null sur une liste vide : il n’y a rien à enregistrer', () => {
    expect(predicatUtile({ operateur: 'eq', valeurs: ['commune'] }, { operateur: 'in', valeurs: [] })).toBeNull();
  });
});

describe('phraseLisible', () => {
  it('écrit une phrase, pas du JSON', () => {
    expect(phraseLisible('Quel est le statut du porteur ?', 'in', ['association', 'commune'], REPONSES)).toBe(
      'Quel est le statut du porteur ? est parmi Association, Commune',
    );
  });

  it('retombe sur l’identifiant quand la réponse a disparu', () => {
    expect(phraseLisible('Statut ?', 'eq', ['parti'], REPONSES)).toBe('Statut ? est parti');
  });

  it('rend un tiret sans opérateur ni valeur', () => {
    expect(phraseLisible('Statut ?', '', [], REPONSES)).toBe('—');
  });
});

describe('filtrerConditions', () => {
  it('cherche sur l’aide, le texte et la question, accents normalisés', () => {
    const liste = [condition()];
    expect(filtrerConditions(liste, 'DRAC')).toHaveLength(1);
    expect(filtrerConditions(liste, 'association')).toHaveLength(1);
    expect(filtrerConditions(liste, 'statut du porteur')).toHaveLength(1);
    expect(filtrerConditions(liste, 'toiture')).toHaveLength(0);
  });

  it('rend tout sur une recherche vide', () => {
    expect(filtrerConditions([condition()], '   ')).toHaveLength(1);
  });
});

describe('inventaireSurcharges', () => {
  it('ne garde que les conditions surchargées, plus les orphelines', () => {
    const liste = [condition(), condition({ conditionId: 'b', surcharge: surcharge('active') })];
    const orpheline: ConditionOrpheline = {
      aideSlug: 'aide-archivee',
      conditionId: 'c1',
      surcharge: surcharge('aide_absente'),
    };
    const inventaire = inventaireSurcharges(liste, [orpheline]);
    expect(inventaire.map((l) => l.conditionId)).toEqual(['c1', 'b']);
  });

  it('remonte les périmées en tête : ce sont elles qui demandent une action', () => {
    const liste = [
      condition({ conditionId: 'ok', surcharge: surcharge('active') }),
      condition({ conditionId: 'revoir', surcharge: surcharge('a_revoir') }),
      condition({ conditionId: 'perimee', surcharge: surcharge('perimee_texte') }),
    ];
    expect(inventaireSurcharges(liste, []).map((l) => l.conditionId)).toEqual([
      'perimee',
      'revoir',
      'ok',
    ]);
  });
});
