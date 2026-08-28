import { create } from 'zustand';
import type { Projet } from '@/types';

interface ProjetState {
  projets: Projet[];
  loaded: boolean;

  setProjets: (projets: Projet[]) => void;
  getProjet: (id: string) => Projet | undefined;
  getProjetsByMonument: (monumentId: string) => Projet[];
  addProjet: (projet: Projet) => void;
  /** Remplace le projet s'il est déjà là (rafraîchissement serveur), sinon l'ajoute. */
  upsertProjet: (projet: Projet) => void;
  deleteProjet: (id: string) => void;
}

export const useProjetStore = create<ProjetState>()((set, get) => ({
  projets: [],
  loaded: false,

  setProjets: (projets) => set({ projets, loaded: true }),

  getProjet: (id) => get().projets.find((p) => p.id === id),

  getProjetsByMonument: (monumentId) =>
    get().projets.filter((p) => p.monumentId === monumentId),

  addProjet: (projet) => set((state) => ({ projets: [projet, ...state.projets] })),

  upsertProjet: (projet) =>
    set((state) =>
      state.projets.some((p) => p.id === projet.id)
        ? { projets: state.projets.map((p) => (p.id === projet.id ? projet : p)) }
        : { projets: [projet, ...state.projets] }
    ),

  deleteProjet: (id) =>
    set((state) => ({ projets: state.projets.filter((p) => p.id !== id) })),
}));
