import { describe, expect, it } from 'vitest';
import { computeEliminatedAideIds } from '../qcm';
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
