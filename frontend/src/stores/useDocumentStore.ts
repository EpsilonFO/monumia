import { create } from 'zustand';
import type { Document, DocumentType } from '@/types';
import { mockDocuments } from '@/data/mock-documents';
import { generateId } from '@/lib/format-utils';

interface DocumentState {
  documents: Document[];

  getDocument: (id: string) => Document | undefined;
  getDocumentsByUser: (userId: string) => Document[];
  getDocumentsByMonument: (monumentId: string) => Document[];
  getDocumentsByType: (type: DocumentType) => Document[];
  getDocumentsForDossier: (dossierId: string) => Document[];
  addDocument: (doc: Omit<Document, 'id' | 'dateUpload'>) => Document;
  updateDocument: (id: string, updates: Partial<Document>) => void;
  deleteDocument: (id: string) => void;
  linkToDossier: (documentId: string, dossierId: string) => void;
  unlinkFromDossier: (documentId: string, dossierId: string) => void;
}

export const useDocumentStore = create<DocumentState>()((set, get) => ({
  documents: mockDocuments,

  getDocument: (id) => get().documents.find((d) => d.id === id),

  getDocumentsByUser: (userId) =>
    get().documents.filter((d) => d.userId === userId),

  getDocumentsByMonument: (monumentId) =>
    get().documents.filter((d) => d.monumentId === monumentId),

  getDocumentsByType: (type) =>
    get().documents.filter((d) => d.type === type),

  getDocumentsForDossier: (dossierId) =>
    get().documents.filter((d) => d.dossiersUtilises.includes(dossierId)),

  addDocument: (doc) => {
    const newDoc: Document = {
      ...doc,
      id: `doc-${generateId()}`,
      dateUpload: new Date().toISOString(),
    };
    set((state) => ({ documents: [...state.documents, newDoc] }));
    return newDoc;
  },

  updateDocument: (id, updates) =>
    set((state) => ({
      documents: state.documents.map((d) =>
        d.id === id ? { ...d, ...updates } : d
      ),
    })),

  deleteDocument: (id) =>
    set((state) => ({
      documents: state.documents.filter((d) => d.id !== id),
    })),

  linkToDossier: (documentId, dossierId) =>
    set((state) => ({
      documents: state.documents.map((d) =>
        d.id === documentId && !d.dossiersUtilises.includes(dossierId)
          ? { ...d, dossiersUtilises: [...d.dossiersUtilises, dossierId] }
          : d
      ),
    })),

  unlinkFromDossier: (documentId, dossierId) =>
    set((state) => ({
      documents: state.documents.map((d) =>
        d.id === documentId
          ? {
              ...d,
              dossiersUtilises: d.dossiersUtilises.filter(
                (id) => id !== dossierId
              ),
            }
          : d
      ),
    })),
}));
