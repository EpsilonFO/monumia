import { create } from 'zustand';
import type { Aide, AideDiagnosticResult, AideCategory, WorkType } from '@/types';
import { mockAides } from '@/data/mock-aides';

interface AideFilters {
  categories: AideCategory[];
  travauxFiltres: WorkType[];
  modeProjet: boolean;
  searchQuery: string;
}

interface AideState {
  aides: Aide[];
  filters: AideFilters;
  lastDiagnostic: AideDiagnosticResult | null;

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
  aides: mockAides,
  filters: defaultFilters,
  lastDiagnostic: null,

  setFilters: (updates) =>
    set((state) => ({
      filters: { ...state.filters, ...updates },
    })),

  resetFilters: () => set({ filters: defaultFilters }),

  setLastDiagnostic: (result) => set({ lastDiagnostic: result }),

  clearDiagnostic: () => set({ lastDiagnostic: null }),

  getAide: (id) => get().aides.find((a) => a.id === id),
}));
