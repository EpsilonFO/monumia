import { create } from 'zustand';
import type { AideDiagnosticResult, ProjectDigest } from '@/types';

interface AideState {
  diagnosticsByMonument: Record<string, AideDiagnosticResult>;
  /**
   * Digests par projet, servis en bloc par `GET /dashboard`. Volontairement
   * distincts de `diagnosticsByMonument` : un digest ne porte pas les aides non
   * éligibles ni le détail des conditions, et écraserait un diagnostic complet
   * dont la page projet a besoin.
   */
  digestsByMonument: Record<string, ProjectDigest>;

  setDigests: (digests: Record<string, ProjectDigest>) => void;
  setDiagnostic: (monumentId: string, result: AideDiagnosticResult) => void;
  getDiagnostic: (monumentId: string) => AideDiagnosticResult | undefined;
  clearDiagnostic: (monumentId?: string) => void;
}

export const useAideStore = create<AideState>()((set, get) => ({
  diagnosticsByMonument: {},
  digestsByMonument: {},

  setDigests: (digests) => set({ digestsByMonument: digests }),

  setDiagnostic: (monumentId, result) =>
    set((state) => ({
      diagnosticsByMonument: {
        ...state.diagnosticsByMonument,
        [monumentId]: result,
      },
    })),

  getDiagnostic: (monumentId) => get().diagnosticsByMonument[monumentId],

  clearDiagnostic: (monumentId) =>
    set((state) => {
      if (monumentId) {
        const { [monumentId]: _, ...rest } = state.diagnosticsByMonument;
        return { diagnosticsByMonument: rest };
      }
      return { diagnosticsByMonument: {} };
    }),
}));
