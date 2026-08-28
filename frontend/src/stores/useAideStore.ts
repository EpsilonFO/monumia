import { create } from 'zustand';
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

export const useAideStore = create<AideState>()((set, get) => ({
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
}));
