import { describe, it, expect } from 'vitest';
import { computeProfileCompletion } from '../profile-completion';
import type { User } from '@/types';

const base = {
  id: '1',
  email: 'jean@exemple.fr',
  prenom: 'Jean',
  nom: 'Dupont',
  segment: 'prive',
} as unknown as User;

describe('computeProfileCompletion', () => {
  it('renvoie 100% et aucune manque quand tout est rempli', () => {
    const u = { ...base, telephone: '06 12 34 56 78' } as User;
    const r = computeProfileCompletion(u);
    expect(r.percent).toBe(100);
    expect(r.missing).toEqual([]);
  });

  it('descend et signale le téléphone manquant', () => {
    const u = { ...base, telephone: '' } as User;
    const r = computeProfileCompletion(u);
    expect(r.percent).toBe(67);
    expect(r.missing).toContain('votre téléphone');
  });

  it('ignore les espaces (valeurs blanches = non remplies)', () => {
    const u = { ...base, prenom: '   ', telephone: '0612345678' } as User;
    const r = computeProfileCompletion(u);
    expect(r.missing).toContain('votre prénom');
    expect(r.percent).toBe(67);
  });
});
