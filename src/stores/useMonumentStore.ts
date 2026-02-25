import { create } from 'zustand';
import type { Monument, MonumentPhoto } from '@/types';
import { mockMonuments } from '@/data/mock-monuments';

interface MonumentState {
  monuments: Monument[];
  activeMonumentId: string | null;

  setActiveMonument: (id: string | null) => void;
  getMonument: (id: string) => Monument | undefined;
  getMonumentsByUser: (userId: string) => Monument[];
  addMonument: (monument: Monument) => void;
  updateMonument: (id: string, updates: Partial<Monument>) => void;
  deleteMonument: (id: string) => void;
  addPhoto: (monumentId: string, photo: MonumentPhoto) => void;
  removePhoto: (monumentId: string, photoId: string) => void;
}

export const useMonumentStore = create<MonumentState>()((set, get) => ({
  monuments: mockMonuments,
  activeMonumentId: null,

  setActiveMonument: (id) => set({ activeMonumentId: id }),

  getMonument: (id) => get().monuments.find((m) => m.id === id),

  getMonumentsByUser: (userId) =>
    get().monuments.filter((m) => m.userId === userId),

  addMonument: (monument) =>
    set((state) => ({ monuments: [...state.monuments, monument] })),

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
