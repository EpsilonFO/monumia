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
  lastDiagnostic: AideDiagnosticResult | null;

  setAides: (aides: Aide[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setFilters: (filters: Partial<AideFilters>) => void;
  resetFilters: () => void;
  setLastDiagnostic: (result: AideDiagnosticResult) => void;
  clearDiagnostic: () => void;
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
  lastDiagnostic: null,

  setAides: (aides) => set({ aides, loading: false, error: null }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error, loading: false }),

  setFilters: (updates) =>
    set((state) => ({
      filters: { ...state.filters, ...updates },
    })),

  resetFilters: () => set({ filters: defaultFilters }),

  setLastDiagnostic: (result) => set({ lastDiagnostic: result }),

  clearDiagnostic: () => set({ lastDiagnostic: null }),

  getAide: (id) => get().aides.find((a) => a.id === id),
}));
