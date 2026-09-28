import { describe, expect, it, vi } from 'vitest';
import { actionsDocument } from '../actions-document';
import type { Document } from '@/types';

const doc = (over: Partial<Document> = {}): Document => ({
  id: 'd1', monumentIds: ['m1'], projetIds: [], userId: 'u2', nom: 'x', nomFichier: 'x.pdf', type: 'autre',
  tags: [], tailleFichier: 1, mimeType: 'application/pdf', url: 'u2/x.pdf', dossiersUtilises: [],
  dateUpload: '2026-09-01', visibility: 'team', allowedUserIds: [], ...over,
});
const gestes = () => ({ modifier: vi.fn(), rattacher: vi.fn(), gererAcces: vi.fn(), corbeille: vi.fn(), retirer: vi.fn() });
const labels = (a: { label: string }[]) => a.map((x) => x.label);
const ici = { type: 'monument' as const, id: 'm1', nom: 'Église' };

describe('actionsDocument', () => {
  it("l'auteur modifie, gère l'accès et jette", () => {
    expect(labels(actionsDocument(doc({ userId: 'u1' }), { userId: 'u1', role: 'member', ici }, gestes()))).toEqual([
      'Renommer ou changer le type', 'Rattacher à un autre monument', "Gérer l'accès", 'Mettre à la corbeille',
    ]);
  });

  it("un co_owner non auteur retire d'ici, il ne jette pas", () => {
    const g = gestes();
    const a = actionsDocument(doc(), { userId: 'u1', role: 'co_owner', ici }, g);
    expect(labels(a)).toEqual(['Renommer ou changer le type', 'Rattacher à un autre monument', "Gérer l'accès", 'Retirer de Église']);
    a[3].onClick();
    expect(g.retirer).toHaveBeenCalledWith(expect.objectContaining({ id: 'd1' }), ici);
  });

  it("un simple membre non auteur ne peut que rattacher", () => {
    expect(labels(actionsDocument(doc(), { userId: 'u1', role: 'member', ici }, gestes()))).toEqual([
      'Rattacher à un autre monument',
    ]);
  });

  it("côté projet, on retire du projet ce qui y pend", () => {
    const iciP = { type: 'projet' as const, id: 'p1', nom: 'Toiture' };
    const a = actionsDocument(doc({ monumentIds: [], projetIds: ['p1'] }), { userId: 'u1', role: 'co_owner', ici: iciP }, gestes());
    expect(labels(a)).toContain('Retirer de Toiture');
  });

  it("pas d'accès à régler sur un document sans monument ni projet", () => {
    const a = actionsDocument(doc({ userId: 'u1', monumentIds: [] }), { userId: 'u1', role: null, ici: null }, gestes());
    expect(labels(a)).not.toContain("Gérer l'accès");
  });
});
