import { describe, expect, it } from 'vitest';
import { compterChecklist } from '../checklist-progress';
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
