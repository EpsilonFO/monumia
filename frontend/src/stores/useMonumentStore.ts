import { create } from 'zustand';
import type { Monument, MonumentPhoto } from '@/types';

interface MonumentState {
  monuments: Monument[];
  activeMonumentId: string | null;

  setMonuments: (monuments: Monument[]) => void;
  setActiveMonument: (id: string | null) => void;
  getMonument: (id: string) => Monument | undefined;
  addMonument: (monument: Monument) => void;
  upsertMonument: (monument: Monument) => void;
  updateMonument: (id: string, updates: Partial<Monument>) => void;
  deleteMonument: (id: string) => void;
  addPhoto: (monumentId: string, photo: MonumentPhoto) => void;
  removePhoto: (monumentId: string, photoId: string) => void;
}

export const useMonumentStore = create<MonumentState>()((set, get) => ({
  monuments: [],
  activeMonumentId: null,

  setMonuments: (monuments) => set({ monuments }),

  setActiveMonument: (id) => set({ activeMonumentId: id }),

  getMonument: (id) => get().monuments.find((m) => m.id === id),

  addMonument: (monument) =>
    set((state) => ({ monuments: [monument, ...state.monuments] })),

  // Remplace le monument s'il est déjà présent (rafraîchissement serveur),
  // sinon l'ajoute. Préserve les valeurs serveur (pas d'écrasement d'updatedAt).
  upsertMonument: (monument) =>
    set((state) =>
      state.monuments.some((m) => m.id === monument.id)
        ? { monuments: state.monuments.map((m) => (m.id === monument.id ? monument : m)) }
        : { monuments: [monument, ...state.monuments] }
    ),

  updateMonument: (id, updates) =>
    set((state) => ({
      monuments: state.monuments.map((m) =>
        m.id === id
          ? { ...m, ...updates, updatedAt: new Date().toISOString() }
          : m
      ),
    })),

  deleteMonument: (id) =>
    set((state) => ({
      monuments: state.monuments.filter((m) => m.id !== id),
      activeMonumentId:
        state.activeMonumentId === id ? null : state.activeMonumentId,
    })),

  addPhoto: (monumentId, photo) =>
    set((state) => ({
      monuments: state.monuments.map((m) =>
        m.id === monumentId
          ? { ...m, photos: [...m.photos, photo], updatedAt: new Date().toISOString() }
          : m
      ),
    })),

  removePhoto: (monumentId, photoId) =>
    set((state) => ({
      monuments: state.monuments.map((m) =>
        m.id === monumentId
          ? {
              ...m,
              photos: m.photos.filter((p) => p.id !== photoId),
              updatedAt: new Date().toISOString(),
            }
          : m
      ),
    })),
}));
