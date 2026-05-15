import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Prospect, ProspectStatus, ID } from '@/types';

interface ProspectState {
  prospects: Prospect[];
  getProspect: (id: ID) => Prospect | undefined;
  getProspectsByUser: (btpUserId: ID) => Prospect[];
  getProspectsByStatus: (status: ProspectStatus) => Prospect[];
  addProspect: (prospect: Prospect) => void;
  updateProspect: (id: ID, updates: Partial<Prospect>) => void;
  deleteProspect: (id: ID) => void;
  updateStatut: (id: ID, statut: ProspectStatus) => void;
}

export const useProspectStore = create<ProspectState>()(
  persist(
    (set, get) => ({
      prospects: [],

      getProspect: (id) => get().prospects.find((p) => p.id === id),

      getProspectsByUser: (btpUserId) =>
        get().prospects.filter((p) => p.btpUserId === btpUserId),

      getProspectsByStatus: (status) =>
        get().prospects.filter((p) => p.statut === status),

      addProspect: (prospect) =>
        set((state) => ({ prospects: [...state.prospects, prospect] })),

      updateProspect: (id, updates) =>
        set((state) => ({
          prospects: state.prospects.map((p) =>
            p.id === id ? { ...p, ...updates, updatedAt: new Date().toISOString() } : p
          ),
        })),

      deleteProspect: (id) =>
        set((state) => ({
          prospects: state.prospects.filter((p) => p.id !== id),
        })),

      updateStatut: (id, statut) =>
        set((state) => ({
          prospects: state.prospects.map((p) =>
            p.id === id ? { ...p, statut, updatedAt: new Date().toISOString() } : p
          ),
        })),
    }),
    { name: 'patrys-prospects' }
  )
);
