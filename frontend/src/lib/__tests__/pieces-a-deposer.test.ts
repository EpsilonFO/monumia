import { describe, expect, it } from 'vitest';
import { nbAidesParPiece, piecesADeposer } from '../pieces-a-deposer';
import type { Document, PieceDemandee, ProjectDigest } from '@/types';

function piece(pieceId: string, aideIds: string[], portee: PieceDemandee['portee'] = 'operation'): PieceDemandee {
  return { pieceId, nom: pieceId, description: null, typeDocument: 'autre', portee, aideIds };
}

function digest(projetId: string, pieces: PieceDemandee[]): ProjectDigest {
  return {
    projetId,
    monumentId: 'm1',
    aidesEligibles: [],
    aidesPotentiellementEligibles: [],
    piecesDemandees: pieces,
  };
}

function doc(over: Partial<Document>): Document {
  return {
    id: 'd',
    monumentIds: [],
    projetIds: [],
    userId: 'u1',
    nom: 'x',
    nomFichier: 'x.pdf',
    type: 'autre',
    tags: [],
    tailleFichier: 1,
    mimeType: 'application/pdf',
    url: 'u1/x.pdf',
    dossiersUtilises: [],
    dateUpload: '2026-09-01',
    visibility: 'team',
    allowedUserIds: [],
    ...over,
  };
}

const base = { monumentId: 'm1', projetsDuMonument: ['p1', 'p2', 'p3'], userId: 'u1' };

describe('piecesADeposer', () => {
  it("fait l'union des aides sur les projets, sans compter deux fois la même", () => {
    const res = piecesADeposer({
      ...base,
      digests: {
        p1: digest('p1', [piece('rib', ['a1', 'a2']), piece('devis_travaux', ['a1'])]),
        p2: digest('p2', [piece('rib', ['a2', 'a3'])]),
      },
      projetIds: ['p1', 'p2'],
      documents: [],
    });
    expect(res.map((p) => [p.pieceId, p.nbAides])).toEqual([
      ['rib', 3],
      ['devis_travaux', 1],
    ]);
  });

  it('ignore les projets hors périmètre et les digests absents', () => {
    const res = piecesADeposer({
      ...base,
      digests: { p1: digest('p1', [piece('rib', ['a1'])]), p3: digest('p3', [piece('statuts_structure', ['a9'])]) },
      projetIds: ['p1', 'p2'],
      documents: [],
    });
    expect(res.map((p) => p.pieceId)).toEqual(['rib']);
  });

  it('marque déposée une pièce portée par un document du monument ou de ses projets, en fin de liste', () => {
    const res = piecesADeposer({
      ...base,
      digests: { p1: digest('p1', [piece('devis_travaux', ['a1', 'a2']), piece('plans_projet', ['a1'])]) },
      projetIds: ['p1'],
      documents: [doc({ id: 'd1', pieceId: 'devis_travaux', projetIds: ['p2'], userId: 'u2' })],
    });
    expect(res.map((p) => [p.pieceId, p.deposee])).toEqual([
      ['plans_projet', false],
      ['devis_travaux', true],
    ]);
    expect(res[1].documentIds).toEqual(['d1']);
  });

  it("ne compte pas un document d'un autre monument, ni un document à la corbeille", () => {
    const res = piecesADeposer({
      ...base,
      digests: { p1: digest('p1', [piece('devis_travaux', ['a1'])]) },
      projetIds: ['p1'],
      documents: [
        doc({ id: 'd1', pieceId: 'devis_travaux', monumentIds: ['m2'] }),
        doc({ id: 'd2', pieceId: 'devis_travaux', monumentIds: ['m1'], trashedAt: '2026-09-02' }),
      ],
    });
    expect(res[0].deposee).toBe(false);
  });

  it("une pièce porteur déposée par l'utilisateur ailleurs compte, celle d'un autre non", () => {
    const digests = { p1: digest('p1', [piece('rib', ['a1'], 'porteur')]) };
    const ailleurs = doc({ id: 'd1', pieceId: 'rib', monumentIds: ['m2'] });
    expect(piecesADeposer({ ...base, digests, projetIds: ['p1'], documents: [ailleurs] })[0].deposee).toBe(true);
    expect(
      piecesADeposer({ ...base, digests, projetIds: ['p1'], documents: [{ ...ailleurs, userId: 'u2' }] })[0].deposee,
    ).toBe(false);
  });

  it('rend la table pieceId → nombre d’aides', () => {
    const res = piecesADeposer({
      ...base,
      digests: { p1: digest('p1', [piece('rib', ['a1', 'a2'])]) },
      projetIds: ['p1'],
      documents: [],
    });
    expect(nbAidesParPiece(res)).toEqual({ rib: 2 });
  });
});
