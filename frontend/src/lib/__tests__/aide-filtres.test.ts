import { describe, expect, it } from 'vitest';
import {
  AIDE_FILTRES,
  filtrerAides,
  filtresDisponibles,
  matchFiltre,
  type AideFiltreKey,
} from '@/lib/aide-filtres';
import { AIDE_CATEGORIES } from '@/constants/aide-categories';
import type { AideCategory, AideMatchResult } from '@/types';

function match(id: string, categorie: AideCategory): AideMatchResult {
  return {
    aide: { id, categorie },
    eligible: true,
    criteresRemplis: [],
    criteresNonRemplis: [],
  } as unknown as AideMatchResult;
}

const filtre = (key: AideFiltreKey) => AIDE_FILTRES.find((f) => f.key === key)!;

describe('couverture des filtres', () => {
  it('chaque catégorie du catalogue tombe dans exactement un groupe', () => {
    // Sans quoi une aide disparaîtrait de toutes les vues filtrées — ou
    // apparaîtrait deux fois, avec des comptes qui ne totalisent pas.
    for (const { value } of AIDE_CATEGORIES) {
      const groupes = AIDE_FILTRES.filter(
        (f) => f.categories.length > 0 && f.categories.includes(value),
      );
      expect(groupes.map((g) => g.key), `catégorie ${value}`).toHaveLength(1);
    }
  });

  it('« Toutes les aides » vient en premier et ne filtre rien', () => {
    expect(AIDE_FILTRES[0].key).toBe('toutes');
    expect(AIDE_FILTRES[0].categories).toEqual([]);
  });
});

describe('matchFiltre', () => {
  it('« Toutes les aides » accepte n’importe quelle catégorie', () => {
    expect(matchFiltre(match('a', 'europe'), filtre('toutes'))).toBe(true);
  });

  it('« Prix et mécènes » rassemble fondations ET mécénat', () => {
    expect(matchFiltre(match('a', 'fondation'), filtre('prix_mecenat'))).toBe(true);
    expect(matchFiltre(match('b', 'mecenat'), filtre('prix_mecenat'))).toBe(true);
    expect(matchFiltre(match('c', 'region'), filtre('prix_mecenat'))).toBe(false);
  });

  it('les collectivités restent distinctes', () => {
    expect(matchFiltre(match('a', 'region'), filtre('departement'))).toBe(false);
    expect(matchFiltre(match('b', 'departement'), filtre('region'))).toBe(false);
  });
});

describe('filtrerAides', () => {
  const aides = [
    match('a1', 'region'),
    match('a2', 'departement'),
    match('a3', 'fondation'),
    match('a4', 'mecenat'),
  ];

  it('ne garde que le groupe demandé', () => {
    expect(filtrerAides(aides, filtre('prix_mecenat')).map((m) => m.aide.id)).toEqual(['a3', 'a4']);
  });

  it('rend la liste telle quelle pour « Toutes les aides »', () => {
    expect(filtrerAides(aides, filtre('toutes'))).toBe(aides);
  });

  it('préserve l’ordre d’entrée (tri par échéance calculé en amont)', () => {
    const ordonnees = [match('z', 'region'), match('a', 'region')];
    expect(filtrerAides(ordonnees, filtre('region')).map((m) => m.aide.id)).toEqual(['z', 'a']);
  });
});

describe('filtresDisponibles', () => {
  it('n’affiche que les groupes qui contiennent quelque chose', () => {
    const options = filtresDisponibles(
      [match('a1', 'region'), match('a2', 'fondation')],
      'toutes',
    );
    expect(options.map((o) => o.key)).toEqual(['toutes', 'prix_mecenat', 'region']);
  });

  it('compte les aides de chaque groupe, « toutes » portant le total', () => {
    const options = filtresDisponibles(
      [match('a1', 'region'), match('a2', 'region'), match('a3', 'mecenat')],
      'toutes',
    );
    expect(Object.fromEntries(options.map((o) => [o.key, o.count]))).toEqual({
      toutes: 3,
      prix_mecenat: 1,
      region: 2,
    });
  });

  it('ne propose rien quand un seul groupe est représenté', () => {
    // Une barre à un seul onglet ne filtre rien : elle n'a pas lieu d'être.
    expect(filtresDisponibles([match('a1', 'region'), match('a2', 'region')], 'toutes')).toEqual([]);
  });

  it('ne propose rien sans aucune aide', () => {
    expect(filtresDisponibles([], 'toutes')).toEqual([]);
  });

  it('conserve le groupe sélectionné même devenu vide', () => {
    // Sinon l'onglet qu'on vient de choisir disparaîtrait sous les doigts,
    // laissant la page filtrée sans moyen visible de revenir en arrière.
    const options = filtresDisponibles(
      [match('a1', 'region'), match('a2', 'fondation')],
      'europe',
    );
    const europe = options.find((o) => o.key === 'europe');
    expect(europe).toBeDefined();
    expect(europe?.count).toBe(0);
  });
});
