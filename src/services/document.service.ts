import type { Document, DocumentType } from '@/types';
import { useDocumentStore } from '@/stores/useDocumentStore';

export const documentService = {
  getAll(): Document[] {
    return useDocumentStore.getState().documents;
  },

  getById(id: string): Document | undefined {
    return useDocumentStore.getState().getDocument(id);
  },

  getByUser(userId: string): Document[] {
    return useDocumentStore.getState().getDocumentsByUser(userId);
  },

  getByMonument(monumentId: string): Document[] {
    return useDocumentStore.getState().getDocumentsByMonument(monumentId);
  },

  getByType(type: DocumentType): Document[] {
    return useDocumentStore.getState().getDocumentsByType(type);
  },

  getForDossier(dossierId: string): Document[] {
    return useDocumentStore.getState().getDocumentsForDossier(dossierId);
  },

  upload(doc: Omit<Document, 'id' | 'dateUpload'>): Document {
    return useDocumentStore.getState().addDocument(doc);
  },

  update(id: string, updates: Partial<Document>): void {
    useDocumentStore.getState().updateDocument(id, updates);
  },

  delete(id: string): void {
    useDocumentStore.getState().deleteDocument(id);
  },

  linkToDossier(documentId: string, dossierId: string): void {
    useDocumentStore.getState().linkToDossier(documentId, dossierId);
  },

  unlinkFromDossier(documentId: string, dossierId: string): void {
    useDocumentStore.getState().unlinkFromDossier(documentId, dossierId);
  },

  search(query: string, userId?: string): Document[] {
    const q = query.toLowerCase();
    let docs = useDocumentStore.getState().documents;
    if (userId) {
      docs = docs.filter((d) => d.userId === userId);
    }
    return docs.filter(
      (d) =>
        d.nom.toLowerCase().includes(q) ||
        d.nomFichier.toLowerCase().includes(q) ||
        d.tags.some((t) => t.toLowerCase().includes(q)) ||
        (d.description && d.description.toLowerCase().includes(q))
    );
  },
};
