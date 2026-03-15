import { create } from 'zustand';
import type { Aide, AideDiagnosticResult, AideCategory, WorkType } from '@/types';

interface AideFilters {
  categories: AideCategory[];
  travauxFiltres: WorkType[];
  modeProjet: boolean;
  searchQuery: string;
}

interface AideState {
  aides: Aide[];
  loading: boolean;
  error: string | null;
  filters: AideFilters;
  diagnosticsByMonument: Record<string, AideDiagnosticResult>;
  lastDiagnosticMonumentId: string | null;

  setAides: (aides: Aide[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setFilters: (filters: Partial<AideFilters>) => void;
  resetFilters: () => void;
  setDiagnostic: (monumentId: string, result: AideDiagnosticResult) => void;
  getDiagnostic: (monumentId: string) => AideDiagnosticResult | undefined;
  clearDiagnostic: (monumentId?: string) => void;
  getAide: (id: string) => Aide | undefined;
}

const defaultFilters: AideFilters = {
  categories: [],
  travauxFiltres: [],
  modeProjet: false,
  searchQuery: '',
};

export const useAideStore = create<AideState>()((set, get) => ({
  aides: [],
  loading: false,
  error: null,
  filters: defaultFilters,
  diagnosticsByMonument: {},
  lastDiagnosticMonumentId: null,

  setAides: (aides) => set({ aides, loading: false, error: null }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error, loading: false }),

  setFilters: (updates) =>
    set((state) => ({
      filters: { ...state.filters, ...updates },
    })),

  resetFilters: () => set({ filters: defaultFilters }),

  setDiagnostic: (monumentId, result) =>
    set((state) => ({
      diagnosticsByMonument: {
        ...state.diagnosticsByMonument,
        [monumentId]: result,
      },
      lastDiagnosticMonumentId: monumentId,
    })),

  getDiagnostic: (monumentId) => get().diagnosticsByMonument[monumentId],

  clearDiagnostic: (monumentId) =>
    set((state) => {
      if (monumentId) {
        const { [monumentId]: _, ...rest } = state.diagnosticsByMonument;
        return {
          diagnosticsByMonument: rest,
          lastDiagnosticMonumentId:
            state.lastDiagnosticMonumentId === monumentId
              ? null
              : state.lastDiagnosticMonumentId,
        };
      }
      return { diagnosticsByMonument: {}, lastDiagnosticMonumentId: null };
    }),

  getAide: (id) => get().aides.find((a) => a.id === id),
}));

/** Selector: derive lastDiagnostic from store state */
export function selectLastDiagnostic(s: AideState): AideDiagnosticResult | null {
  if (!s.lastDiagnosticMonumentId) return null;
  return s.diagnosticsByMonument[s.lastDiagnosticMonumentId] ?? null;
}
