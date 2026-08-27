import { create } from 'zustand';
import type { AideSuivi } from '@/types';

/** Suivis d'aide, indexés par PROJET de travaux : le couple unique est
 *  (projet, aide) depuis l'inversion de hiérarchie. */
interface SuiviState {
  suivis: AideSuivi[];
  loadedProjets: Record<string, boolean>;

  setForProjet: (projetId: string, suivis: AideSuivi[]) => void;
  getByProjet: (projetId: string) => AideSuivi[];
  upsert: (suivi: AideSuivi) => void;
  remove: (projetId: string, aideId: string) => void;
}

export const useSuiviStore = create<SuiviState>()((set, get) => ({
  suivis: [],
  loadedProjets: {},

  setForProjet: (projetId, suivis) =>
    set((state) => ({
      suivis: [
        ...state.suivis.filter((s) => s.projetId !== projetId),
        ...suivis,
      ],
      loadedProjets: { ...state.loadedProjets, [projetId]: true },
    })),

  getByProjet: (projetId) =>
    get().suivis.filter((s) => s.projetId === projetId),

  upsert: (suivi) =>
    set((state) => ({
      suivis: [
        ...state.suivis.filter(
          (s) => !(s.projetId === suivi.projetId && s.aideId === suivi.aideId)
        ),
        suivi,
      ],
    })),

  remove: (projetId, aideId) =>
    set((state) => ({
      suivis: state.suivis.filter(
        (s) => !(s.projetId === projetId && s.aideId === aideId)
      ),
    })),
}));
