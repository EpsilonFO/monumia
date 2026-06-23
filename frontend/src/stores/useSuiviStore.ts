import { create } from 'zustand';
import type { AideSuivi } from '@/types';

interface SuiviState {
  suivis: AideSuivi[];
  loadedMonuments: Record<string, boolean>;

  setForMonument: (monumentId: string, suivis: AideSuivi[]) => void;
  getByMonument: (monumentId: string) => AideSuivi[];
  upsert: (suivi: AideSuivi) => void;
  remove: (monumentId: string, aideId: string) => void;
}

export const useSuiviStore = create<SuiviState>()((set, get) => ({
  suivis: [],
  loadedMonuments: {},

  setForMonument: (monumentId, suivis) =>
    set((state) => ({
      suivis: [
        ...state.suivis.filter((s) => s.monumentId !== monumentId),
        ...suivis,
      ],
      loadedMonuments: { ...state.loadedMonuments, [monumentId]: true },
    })),

  getByMonument: (monumentId) =>
    get().suivis.filter((s) => s.monumentId === monumentId),

  upsert: (suivi) =>
    set((state) => ({
      suivis: [
        ...state.suivis.filter(
          (s) => !(s.monumentId === suivi.monumentId && s.aideId === suivi.aideId)
        ),
        suivi,
      ],
    })),

  remove: (monumentId, aideId) =>
    set((state) => ({
      suivis: state.suivis.filter(
        (s) => !(s.monumentId === monumentId && s.aideId === aideId)
      ),
    })),
}));
