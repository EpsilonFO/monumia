import { describe, expect, it } from 'vitest';
import {
  compterParType, documentsRecents, estImage, nomDepuisFichier, rechercherDocuments, tailleTotale, trierDocuments,
} from '../documents-espace';
import { TYPES_DOCUMENT, TYPES_DOSSIERS, dossierLabel } from '../document-type-meta';
import type { Document } from '@/types';

const doc = (over: Partial<Document> = {}): Document => ({
  id: 'd', monumentIds: [], projetIds: [], userId: 'u1', nom: 'x', nomFichier: 'x.pdf', type: 'autre',
  tags: [], tailleFichier: 1, mimeType: 'application/pdf', url: 'u1/x.pdf', dossiersUtilises: [],
  dateUpload: '2026-09-01T10:00:00Z', visibility: 'team', allowedUserIds: [], ...over,
});

describe('dossiers', () => {
  it('un dossier par type, aucun oublié ni en double, « Autres » en dernier', () => {
    expect([...TYPES_DOSSIERS].sort()).toEqual([...TYPES_DOCUMENT].sort());
    expect(new Set(TYPES_DOSSIERS).size).toBe(TYPES_DOSSIERS.length);
    expect(TYPES_DOSSIERS.at(-1)).toBe('autre');
  });

  it('les noms de dossier sont au pluriel', () => {
    expect(dossierLabel('photo')).toBe('Photos');
    expect(dossierLabel('titre_propriete')).toBe('Titres de propriété');
    expect(dossierLabel('devis')).toBe('Devis');
  });
});

describe('rechercherDocuments', () => {
  const docs = [
    doc({ id: 'a', nom: 'Arrêté de protection', type: 'arrete' }),
    doc({ id: 'b', nom: 'Toiture sud', nomFichier: 'devis_martin.pdf', type: 'devis' }),
    doc({ id: 'c', nom: 'Façade', type: 'photo', tags: ['chantier'] }),
  ];
  const ids = (q: string) => rechercherDocuments(docs, q).map((d) => d.id);

  it('sans accents ni casse', () => expect(ids('ARRETE')).toEqual(['a']));
  it('dans le nom de fichier et les étiquettes', () => {
    expect(ids('martin')).toEqual(['b']);
    expect(ids('chantier')).toEqual(['c']);
  });
  it('par le type, au singulier comme au pluriel', () => {
    expect(ids('photos')).toEqual(['c']);
    expect(ids('photo')).toEqual(['c']);
  });
  it('une recherche vide rend tout', () => expect(ids('  ')).toEqual(['a', 'b', 'c']));
});

describe('tri et récents', () => {
  const docs = [
    doc({ id: 'a', nom: 'zèbre', dateUpload: '2026-09-01T10:00:00Z' }),
    doc({ id: 'b', nom: 'Écluse', dateUpload: '2026-09-03T10:00:00Z' }),
    doc({ id: 'c', nom: 'arbre', dateUpload: '2026-09-02T10:00:00Z' }),
  ];

  it('les plus récents d\'abord', () => expect(trierDocuments(docs, 'date').map((d) => d.id)).toEqual(['b', 'c', 'a']));
  it('par nom, à la française', () => expect(trierDocuments(docs, 'nom').map((d) => d.id)).toEqual(['c', 'b', 'a']));
  it('ne modifie pas la liste reçue', () => {
    trierDocuments(docs, 'nom');
    expect(docs.map((d) => d.id)).toEqual(['a', 'b', 'c']);
  });
  it('les récents sont les derniers ajouts', () => expect(documentsRecents(docs, 2).map((d) => d.id)).toEqual(['b', 'c']));
});

describe('compteurs', () => {
  it('par type et poids total', () => {
    const docs = [doc({ type: 'photo', tailleFichier: 100 }), doc({ type: 'photo', tailleFichier: 50 }), doc({ type: 'rib' })];
    expect(compterParType(docs)).toEqual({ photo: 2, rib: 1 });
    expect(tailleTotale(docs)).toBe(151);
  });
});

describe('fichiers', () => {
  it('nom proposé depuis le fichier', () => {
    expect(nomDepuisFichier('devis_toiture-sud.v2.pdf')).toBe('devis toiture sud.v2');
    expect(nomDepuisFichier('Plan de masse.png')).toBe('Plan de masse');
  });
  it('images', () => {
    expect(estImage('JPG')).toBe(true);
    expect(estImage('heic')).toBe(true);
    expect(estImage('PDF', 'application/pdf')).toBe(false);
    expect(estImage('DOC', 'image/png')).toBe(true);
  });
});
