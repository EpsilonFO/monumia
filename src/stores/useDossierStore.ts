import { create } from 'zustand';
import type {
  Dossier,
  DossierStatus,
  ChecklistItem,
  ChecklistItemStatus,
  DossierSection,
  DossierCollaborateur,
  DossierEcheance,
} from '@/types';
import { mockDossiers } from '@/data/mock-dossiers';

interface DossierState {
  dossiers: Dossier[];

  getDossier: (id: string) => Dossier | undefined;
  getDossiersByUser: (userId: string) => Dossier[];
  getDossiersByMonument: (monumentId: string) => Dossier[];
  getDossiersByStatus: (status: DossierStatus) => Dossier[];
  addDossier: (dossier: Dossier) => void;
  updateDossier: (id: string, updates: Partial<Dossier>) => void;
  deleteDossier: (id: string) => void;
  updateChecklistItem: (dossierId: string, itemId: string, statut: ChecklistItemStatus, documentId?: string) => void;
  updateSection: (dossierId: string, sectionId: string, contenu: string) => void;
  addCollaborateur: (dossierId: string, collab: DossierCollaborateur) => void;
  removeCollaborateur: (dossierId: string, collabId: string) => void;
  addEcheance: (dossierId: string, echeance: DossierEcheance) => void;
  toggleEcheance: (dossierId: string, echeanceId: string) => void;
}

function updateDossierInList(
  dossiers: Dossier[],
  id: string,
  updater: (d: Dossier) => Dossier
): Dossier[] {
  return dossiers.map((d) =>
    d.id === id
      ? { ...updater(d), dateDerniereModification: new Date().toISOString() }
      : d
  );
}

export const useDossierStore = create<DossierState>()((set, get) => ({
  dossiers: mockDossiers,

  getDossier: (id) => get().dossiers.find((d) => d.id === id),

  getDossiersByUser: (userId) =>
    get().dossiers.filter((d) => d.userId === userId),

  getDossiersByMonument: (monumentId) =>
    get().dossiers.filter((d) => d.monumentId === monumentId),

  getDossiersByStatus: (status) =>
    get().dossiers.filter((d) => d.statut === status),

  addDossier: (dossier) =>
    set((state) => ({ dossiers: [...state.dossiers, dossier] })),

  updateDossier: (id, updates) =>
    set((state) => ({
      dossiers: updateDossierInList(state.dossiers, id, (d) => ({
        ...d,
        ...updates,
      })),
    })),

  deleteDossier: (id) =>
    set((state) => ({
      dossiers: state.dossiers.filter((d) => d.id !== id),
    })),

  updateChecklistItem: (dossierId, itemId, statut, documentId) =>
    set((state) => ({
      dossiers: updateDossierInList(state.dossiers, dossierId, (d) => ({
        ...d,
        checklist: d.checklist.map((item) =>
          item.id === itemId
            ? { ...item, statut, ...(documentId !== undefined ? { documentId } : {}) }
            : item
        ),
      })),
    })),

  updateSection: (dossierId, sectionId, contenu) =>
    set((state) => ({
      dossiers: updateDossierInList(state.dossiers, dossierId, (d) => ({
        ...d,
        sections: d.sections.map((s) =>
          s.id === sectionId ? { ...s, contenu } : s
        ),
      })),
    })),

  addCollaborateur: (dossierId, collab) =>
    set((state) => ({
      dossiers: updateDossierInList(state.dossiers, dossierId, (d) => ({
        ...d,
        collaborateurs: [...d.collaborateurs, collab],
      })),
    })),

  removeCollaborateur: (dossierId, collabId) =>
    set((state) => ({
      dossiers: updateDossierInList(state.dossiers, dossierId, (d) => ({
        ...d,
        collaborateurs: d.collaborateurs.filter((c) => c.id !== collabId),
      })),
    })),

  addEcheance: (dossierId, echeance) =>
    set((state) => ({
      dossiers: updateDossierInList(state.dossiers, dossierId, (d) => ({
        ...d,
        echeances: [...d.echeances, echeance],
      })),
    })),

  toggleEcheance: (dossierId, echeanceId) =>
    set((state) => ({
      dossiers: updateDossierInList(state.dossiers, dossierId, (d) => ({
        ...d,
        echeances: d.echeances.map((e) =>
          e.id === echeanceId ? { ...e, accomplie: !e.accomplie } : e
        ),
      })),
    })),
}));
