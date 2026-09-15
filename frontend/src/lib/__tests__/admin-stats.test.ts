import { describe, expect, it } from 'vitest';
import {
  NON_CHIFFRE,
  basculerTri,
  filtrerTerritoires,
  formaterCouverture,
  formaterHeure,
  formaterMontant,
  formaterTaux,
  masquerVides,
  trierLignes,
} from '@/lib/admin-stats';
import type { BlocStats, StatsDepartement } from '@/types/admin.types';

/**
 * Les espaces insécables d'`Intl` (avant « % », entre les milliers) varient
 * avec la version d'ICU : les normaliser fait porter l'assertion sur les
 * chiffres, pas sur la typographie du runtime.
 */
function espaces(texte: string): string {
  return texte.replace(/[\u00a0\u202f]/g, ' ');
}

function bloc(over: Partial<BlocStats> = {}): BlocStats {
  return {
    nb: 3,
    retirees: 0,
    typees: 3,
    bientot: 0,
    nbAvecTaux: 2,
    tauxMin: 15,
    tauxMax: 40,
    tauxMedian: 30,
    nbAvecMontant: 1,
    montantMedian: 50000,
    montantMax: 120000,
    ...over,
  };
}

function departement(over: Partial<StatsDepartement> = {}): StatsDepartement {
  return {
    ...bloc(),
    code: '88',
    label: 'Vosges',
    region: 'grand-est',
    regionLabel: 'Grand Est',
    locales: 3,
    conseilDepartemental: 1,
    regionales: 2,
    nationales: 55,
    couverture: 60,
    ...over,
  };
}

describe('formaterTaux', () => {
  it('donne la fourchette quand les deux bornes diffèrent', () => {
    expect(espaces(formaterTaux(bloc()))).toBe('15 à 40 %');
  });

  it('ne répète pas une borne unique', () => {
    expect(espaces(formaterTaux(bloc({ tauxMin: 20, tauxMax: 20 })))).toBe('20 %');
  });

  it('dit « non chiffré » plutôt que zéro quand la source n’annonce rien', () => {
    expect(formaterTaux(bloc({ tauxMin: null, tauxMax: null }))).toBe(NON_CHIFFRE);
  });

  it('affiche un taux réellement nul, qui n’est pas une absence', () => {
    expect(espaces(formaterTaux(bloc({ tauxMin: 0, tauxMax: 0 })))).toBe('0 %');
  });
});

describe('formaterMontant', () => {
  it('distingue l’absence de plafond du plafond nul', () => {
    expect(formaterMontant(null)).toBe(NON_CHIFFRE);
    expect(formaterMontant(0)).not.toBe(NON_CHIFFRE);
  });

  it('formate en euros sans décimale', () => {
    expect(espaces(formaterMontant(50000))).toBe('50 000 €');
  });
});

describe('formaterCouverture', () => {
  it('rapporte les aides chiffrées au total du groupe', () => {
    expect(formaterCouverture(2, 29)).toBe('2 / 29');
  });
});

describe('trierLignes', () => {
  const lignes = [
    departement({ code: '88', label: 'Vosges', locales: 3, montantMax: 120000 }),
    departement({ code: '57', label: 'Moselle', locales: 7, montantMax: null }),
    departement({ code: '08', label: 'Ardennes', locales: 1, montantMax: 900000 }),
  ];

  it('trie les nombres dans les deux sens', () => {
    expect(trierLignes(lignes, { cle: 'locales', sens: 'desc' }).map((l) => l.locales)).toEqual([
      7, 3, 1,
    ]);
    expect(trierLignes(lignes, { cle: 'locales', sens: 'asc' }).map((l) => l.locales)).toEqual([
      1, 3, 7,
    ]);
  });

  it('trie le texte en français, accents compris', () => {
    const noms = ['Éure', 'Ardèche', 'Zonza'];
    const trie = trierLignes(
      noms.map((label) => departement({ label })),
      { cle: 'label', sens: 'asc' },
    );
    expect(trie.map((l) => l.label)).toEqual(['Ardèche', 'Éure', 'Zonza']);
  });

  it('laisse les valeurs absentes en bas, quel que soit le sens', () => {
    // Un plafond non annoncé n'est ni le plus grand ni le plus petit : le
    // remonter en tête d'un tri décroissant cacherait les lignes cherchées.
    for (const sens of ['asc', 'desc'] as const) {
      const trie = trierLignes(lignes, { cle: 'montantMax', sens });
      expect(trie[trie.length - 1].montantMax).toBeNull();
    }
  });

  it('ne modifie pas le tableau reçu', () => {
    const copie = [...lignes];
    trierLignes(lignes, { cle: 'locales', sens: 'asc' });
    expect(lignes).toEqual(copie);
  });
});

describe('basculerTri', () => {
  it('inverse le sens sur la même colonne', () => {
    expect(basculerTri({ cle: 'locales', sens: 'desc' }, 'locales', 'desc')).toEqual({
      cle: 'locales',
      sens: 'asc',
    });
  });

  it('repart du sens par défaut en changeant de colonne', () => {
    expect(basculerTri({ cle: 'locales', sens: 'asc' }, 'label', 'asc')).toEqual({
      cle: 'label',
      sens: 'asc',
    });
  });
});

describe('filtrerTerritoires', () => {
  const lignes = [
    departement({ code: '88', label: 'Vosges', regionLabel: 'Grand Est' }),
    departement({ code: '35', label: 'Ille-et-Vilaine', regionLabel: 'Bretagne' }),
  ];

  it('cherche sur le code INSEE', () => {
    expect(filtrerTerritoires(lignes, '88').map((l) => l.label)).toEqual(['Vosges']);
  });

  it('cherche sur la région, accents et casse ignorés', () => {
    expect(filtrerTerritoires(lignes, 'bretagne').map((l) => l.code)).toEqual(['35']);
  });

  it('trouve « Ille » sans se laisser arrêter par les accents', () => {
    expect(filtrerTerritoires(lignes, 'ille-et-vilaine')).toHaveLength(1);
  });

  it('rend tout sur une recherche vide', () => {
    expect(filtrerTerritoires(lignes, '   ')).toHaveLength(2);
  });
});

describe('masquerVides', () => {
  const lignes = [departement({ nb: 0 }), departement({ nb: 4 })];

  it('garde les territoires sans aide tant que le masquage est inactif', () => {
    expect(masquerVides(lignes, false)).toHaveLength(2);
  });

  it('ne garde que les territoires couverts une fois actif', () => {
    expect(masquerVides(lignes, true).map((l) => l.nb)).toEqual([4]);
  });
});

describe('formaterHeure', () => {
  it('rend une heure lisible', () => {
    expect(formaterHeure('2026-09-15T12:34:56Z')).toMatch(/^\d{2}:\d{2}:\d{2}$/);
  });

  it('ne casse pas sur une date illisible', () => {
    expect(formaterHeure('pas une date')).toBe('');
  });
});
