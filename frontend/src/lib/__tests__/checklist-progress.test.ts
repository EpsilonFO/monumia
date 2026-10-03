import { describe, expect, it } from 'vitest';
import { compterChecklist, progressionDossier } from '../checklist-progress';
import type { ChecklistItem } from '@/types';

function item(statut: ChecklistItem['statut'], id = Math.random().toString()): ChecklistItem {
  return {
    id,
    label: 'Pièce',
    description: '',
    statut,
    obligatoire: true,
    categorie: 'document',
    ordre: 1,
  };
}

describe('compterChecklist', () => {
  it('ne compte que les pièces fournies comme confirmées', () => {
    const res = compterChecklist([item('fourni'), item('repris'), item('manquant')]);
    expect(res.confirmees).toBe(1);
  });

  it('compte les pièces reprises à part', () => {
    const res = compterChecklist([item('repris'), item('repris'), item('manquant')]);
    expect(res.aVerifier).toBe(2);
  });

  it('le total couvre toutes les pièces', () => {
    const res = compterChecklist([item('fourni'), item('repris'), item('en_attente')]);
    expect(res.total).toBe(3);
  });

  it('gère une checklist vide', () => {
    expect(compterChecklist([])).toEqual({ confirmees: 0, aVerifier: 0, total: 0 });
  });
});

describe('progressionDossier', () => {
  const facultative = (statut: ChecklistItem['statut']) => ({ ...item(statut), obligatoire: false });

  it('compte toutes les pièces, pas seulement les obligatoires', () => {
    // Trois obligatoires fournies, une facultative fournie, huit à réunir :
    // 4 / 12, comme sur la page du dossier, et non 100 %.
    const checklist = [
      item('fourni'),
      item('fourni'),
      item('fourni'),
      facultative('fourni'),
      ...Array.from({ length: 8 }, () => facultative('manquant')),
    ];
    expect(progressionDossier({ statut: 'en_cours', checklist })).toBe(33);
  });

  it('une pièce reprise ne compte pas avant confirmation', () => {
    expect(progressionDossier({ statut: 'en_cours', checklist: [item('fourni'), item('repris')] })).toBe(50);
  });

  it('un dossier déposé est à 100 %, un dossier vide à 0 %', () => {
    expect(progressionDossier({ statut: 'soumis', checklist: [item('manquant')] })).toBe(100);
    expect(progressionDossier({ statut: 'brouillon', checklist: [] })).toBe(0);
  });
});
