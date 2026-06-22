import { create } from 'zustand';
import type { Document, DocumentType } from '@/types';
import { documentService, type UploadDocumentPayload } from '@/services/document.service';

interface DocumentState {
  documents: Document[];
  loading: boolean;
  error: string | null;

  fetchDocuments: (params?: { monumentId?: string; type?: string }) => Promise<void>;
  uploadDocument: (payload: UploadDocumentPayload, userId: string) => Promise<Document>;
  updateDocument: (
    id: string,
    updates: { nom?: string; type?: string; description?: string; visibility?: Document['visibility']; allowedUserIds?: string[] },
  ) => Promise<void>;
  deleteDocument: (id: string) => Promise<void>;
  addToProjects: (documentId: string, monumentIds: string[]) => Promise<Document>;
  linkToDossier: (documentId: string, dossierId: string) => Promise<void>;
  unlinkFromDossier: (documentId: string, dossierId: string) => Promise<void>;

  // Selectors (sync, from local state)
  getDocument: (id: string) => Document | undefined;
  getDocumentsByMonument: (monumentId: string) => Document[];
  getDocumentsByType: (type: DocumentType) => Document[];
  getDocumentsForDossier: (dossierId: string) => Document[];
}

export const useDocumentStore = create<DocumentState>()((set, get) => ({
  documents: [],
  loading: false,
  error: null,

  fetchDocuments: async (params) => {
    set({ loading: true, error: null });
    try {
      const documents = await documentService.getAll(params);
      set({ documents, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  uploadDocument: async (payload, userId) => {
    const doc = await documentService.upload(payload, userId);
    set((state) => ({ documents: [doc, ...state.documents] }));
    return doc;
  },

  updateDocument: async (id, updates) => {
    const updated = await documentService.update(id, updates);
    set((state) => ({
      documents: state.documents.map((d) => (d.id === id ? updated : d)),
    }));
  },

  deleteDocument: async (id) => {
    await documentService.delete(id);
    set((state) => ({
      documents: state.documents.filter((d) => d.id !== id),
    }));
  },

  addToProjects: async (documentId, monumentIds) => {
    const updated = await documentService.addToProjects(documentId, monumentIds);
    set((state) => ({
      documents: state.documents.map((d) => (d.id === updated.id ? updated : d)),
    }));
    return updated;
  },

  linkToDossier: async (documentId, dossierId) => {
    await documentService.linkToDossier(documentId, dossierId);
    set((state) => ({
      documents: state.documents.map((d) =>
        d.id === documentId && !d.dossiersUtilises.includes(dossierId)
          ? { ...d, dossiersUtilises: [...d.dossiersUtilises, dossierId] }
          : d
      ),
    }));
  },

  unlinkFromDossier: async (documentId, dossierId) => {
    await documentService.unlinkFromDossier(documentId, dossierId);
    set((state) => ({
      documents: state.documents.map((d) =>
        d.id === documentId
          ? { ...d, dossiersUtilises: d.dossiersUtilises.filter((id) => id !== dossierId) }
          : d
      ),
    }));
  },

  getDocument: (id) => get().documents.find((d) => d.id === id),
  getDocumentsByMonument: (monumentId) => get().documents.filter((d) => d.monumentIds.includes(monumentId)),
  getDocumentsByType: (type) => get().documents.filter((d) => d.type === type),
  getDocumentsForDossier: (dossierId) => get().documents.filter((d) => d.dossiersUtilises.includes(dossierId)),
}));
