import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { enregistrerCache, optionsDeCache } from './persistance';
import type { AideDiagnosticResult, ProjectDigest } from '@/types';

/**
 * Diagnostics indexés par PROJET de travaux : deux chantiers d'un même monument
 * ont chacun leur cadrage, donc chacun leur liste d'aides.
 */
interface AideState {
  diagnosticsByProjet: Record<string, AideDiagnosticResult>;
  /**
   * Digests par projet, servis en bloc par `GET /dashboard`. Volontairement
   * distincts de `diagnosticsByProjet` : un digest ne porte pas les aides non
   * éligibles ni le détail des conditions, et écraserait un diagnostic complet
   * dont la page projet a besoin.
   */
  digestsByProjet: Record<string, ProjectDigest>;

  setDigests: (digests: Record<string, ProjectDigest>) => void;
  setDiagnostic: (projetId: string, result: AideDiagnosticResult) => void;
  getDiagnostic: (projetId: string) => AideDiagnosticResult | undefined;
  clearDiagnostic: (projetId?: string) => void;
}

export const useAideStore = create<AideState>()(persist((set, get) => ({
  diagnosticsByProjet: {},
  digestsByProjet: {},

  setDigests: (digests) => set({ digestsByProjet: digests }),

  setDiagnostic: (projetId, result) =>
    set((state) => ({
      diagnosticsByProjet: {
        ...state.diagnosticsByProjet,
        [projetId]: result,
      },
    })),

  getDiagnostic: (projetId) => get().diagnosticsByProjet[projetId],

  clearDiagnostic: (projetId) =>
    set((state) => {
      if (projetId) {
        const { [projetId]: _, ...rest } = state.diagnosticsByProjet;
        return { diagnosticsByProjet: rest };
      }
      return { diagnosticsByProjet: {} };
    }),
}), optionsDeCache<AideState, { digestsByProjet: Record<string, ProjectDigest> }>({
  domaine: 'aides',
  version: 1,
  // Les digests seulement. Un diagnostic complet pèse encore un mégaoctet, et
  // se recalcule en un aller-retour à l'ouverture du projet : le cache n'y
  // gagnerait rien que de la place.
  partialize: (state) => ({ digestsByProjet: state.digestsByProjet }),
})));

enregistrerCache(useAideStore, () =>
  useAideStore.setState({ diagnosticsByProjet: {}, digestsByProjet: {} }),
);
