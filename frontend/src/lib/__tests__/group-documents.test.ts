import { describe, it, expect } from 'vitest';
import { groupDocumentsByProject } from '@/lib/group-documents';
import type { Document } from '@/types';

const doc = (id: string, monumentIds: string[]): Document =>
  ({
    id, monumentIds, projetIds: [], userId: 'u1', nom: id, nomFichier: `${id}.pdf`, type: 'autre',
    tags: [], tailleFichier: 1, mimeType: 'application/pdf', url: 'u1/x.pdf',
    dossiersUtilises: [], dateUpload: '2026-01-01', visibility: 'team', allowedUserIds: [],
  }) as Document;

describe('groupDocumentsByProject', () => {
  it('place un doc multi-projets sous chaque projet', () => {
    const { byProject } = groupDocumentsByProject([doc('d1', ['m1', 'm2'])]);
    expect(byProject.get('m1')?.map((d) => d.id)).toEqual(['d1']);
    expect(byProject.get('m2')?.map((d) => d.id)).toEqual(['d1']);
  });
  it('place un doc sans projet dans sansProjet', () => {
    const { byProject, sansProjet } = groupDocumentsByProject([doc('d2', [])]);
    expect(sansProjet.map((d) => d.id)).toEqual(['d2']);
    expect(byProject.size).toBe(0);
  });
  it('mélange : d1 dans m1, d3 sans projet', () => {
    const { byProject, sansProjet } = groupDocumentsByProject([doc('d1', ['m1']), doc('d3', [])]);
    expect(byProject.get('m1')?.map((d) => d.id)).toEqual(['d1']);
    expect(sansProjet.map((d) => d.id)).toEqual(['d3']);
  });
});
