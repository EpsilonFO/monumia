import { describe, expect, it } from 'vitest';
import { iconForOption } from '../iconForOption';
import {
  IconChantier,
  IconErreur,
  IconMaison,
  IconProtection,
  IconSucces,
} from '@/components/icons';

describe('iconForOption', () => {
  it('mappe les mots-clés de toiture vers IconMaison', () => {
    expect(iconForOption({ id: 'a', label: 'Toiture en ardoise' })).toBe(IconMaison);
  });

  it('normalise les accents (rénovation → chantier)', () => {
    expect(iconForOption({ id: 'b', label: 'Rénovation complète' })).toBe(IconChantier);
  });

  it('mappe oui/non en début de libellé seulement', () => {
    expect(iconForOption({ id: 'c', label: 'Oui' })).toBe(IconSucces);
    expect(iconForOption({ id: 'd', label: 'Non, aucun' })).toBe(IconErreur);
    expect(iconForOption({ id: 'e', label: 'Sinon autre chose' })).toBe(null);
  });

  it('mappe la protection', () => {
    expect(iconForOption({ id: 'f', label: 'Classé Monument Historique' })).toBe(IconProtection);
  });

  it('retourne null sans correspondance', () => {
    expect(iconForOption({ id: 'g', label: 'Peut-être' })).toBe(null);
  });
});
