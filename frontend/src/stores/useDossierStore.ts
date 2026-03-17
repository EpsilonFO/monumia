import { create } from 'zustand';
import type {
  Dossier,
  DossierStatus,
} from '@/types';

interface DossierState {
  dossiers: Dossier[];
  loaded: boolean;

  setDossiers: (dossiers: Dossier[]) => void;
  getDossier: (id: string) => Dossier | undefined;
  getDossiersByUser: (userId: string) => Dossier[];
  getDossiersByMonument: (monumentId: string) => Dossier[];
  getDossiersByStatus: (status: DossierStatus) => Dossier[];
  addDossier: (dossier: Dossier) => void;
  updateDossier: (id: string, updates: Partial<Dossier>) => void;
  deleteDossier: (id: string) => void;
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
  dossiers: [],
  loaded: false,

  setDossiers: (dossiers) => set({ dossiers, loaded: true }),

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
}));
