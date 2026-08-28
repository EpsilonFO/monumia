import { describe, expect, it } from 'vitest';
import { availableProjectsForDocument } from '../document-projects';
import type { Document, Monument } from '@/types';

function makeMonument(id: string, userId: string, nom: string): Monument {
  return {
    id,
    userId,
    nom,
    codeInsee: '00000',
    commune: 'Rodez',
    protection: 'classe',
    proprietaire: 'public_commune',
    etatConservation: 'moyen',
    photos: [],
    completionPercentage: 50,
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
  } as Monument;
}

function makeDoc(monumentIds: string[]): Document {
  return {
    id: 'doc-1',
    monumentIds,
    projetIds: [],
    userId: 'u1',
    nom: 'Doc',
    nomFichier: 'doc.pdf',
    type: 'devis',
    tags: [],
    tailleFichier: 1,
    mimeType: 'application/pdf',
    url: 'u1/doc.pdf',
    dossiersUtilises: [],
    dateUpload: '2026-01-01T00:00:00Z',
    visibility: 'team',
    allowedUserIds: [],
  };
}

describe('availableProjectsForDocument', () => {
  it('returns only the current user projects not already linked', () => {
    const monuments = [
      makeMonument('m1', 'u1', 'Église A'),
      makeMonument('m2', 'u1', 'Chapelle B'),
      makeMonument('m3', 'u2', 'Château autrui'),
    ];
    const result = availableProjectsForDocument(monuments, 'u1', makeDoc(['m1']));
    expect(result.map((m) => m.id)).toEqual(['m2']);
  });

  it('returns an empty array when the doc is in every owned project', () => {
    const monuments = [makeMonument('m1', 'u1', 'Église A')];
    const result = availableProjectsForDocument(monuments, 'u1', makeDoc(['m1']));
    expect(result).toEqual([]);
  });

  it('returns an empty array when document is null', () => {
    const monuments = [makeMonument('m1', 'u1', 'Église A')];
    expect(availableProjectsForDocument(monuments, 'u1', null)).toEqual([]);
  });
});
