import { describe, it, expect } from 'vitest';
import { projectColor, PROJECT_PALETTE } from '@/lib/project-color';

describe('projectColor', () => {
  it('est déterministe', () => {
    expect(projectColor('abc')).toBe(projectColor('abc'));
  });
  it('renvoie une couleur de la palette', () => {
    expect(PROJECT_PALETTE).toContain(projectColor('mon-projet-42'));
  });
  it('distingue des ids différents (pas tous identiques)', () => {
    const colors = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'].map(projectColor);
    expect(new Set(colors).size).toBeGreaterThan(1);
  });
});
