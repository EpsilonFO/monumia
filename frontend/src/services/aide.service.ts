import type { Aide, AideCategory, AideDiagnosticResult, WorkType } from '@/types';
import { useAideStore } from '@/stores/useAideStore';
import { authFetch, handleResponse } from '@/lib/auth-fetch';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export const aideService = {
  async getAll(): Promise<Aide[]> {
    const res = await authFetch(`${BASE}/aides`);
    return handleResponse<Aide[]>(res);
  },

  async getById(id: string): Promise<Aide> {
    const res = await authFetch(`${BASE}/aides/${id}`);
    return handleResponse<Aide>(res);
  },

  async getByCategory(category: AideCategory): Promise<Aide[]> {
    const res = await authFetch(`${BASE}/aides?categorie=${category}`);
    return handleResponse<Aide[]>(res);
  },

  async search(query: string): Promise<Aide[]> {
    const res = await authFetch(`${BASE}/aides?q=${encodeURIComponent(query)}`);
    return handleResponse<Aide[]>(res);
  },

  async runDiagnostic(
    monumentId: string,
    modeProjet: boolean = false,
    travauxFiltres?: WorkType[]
  ): Promise<AideDiagnosticResult> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120_000); // 2 min max
    try {
      const res = await authFetch(`${BASE}/aides/diagnostic`, {
        method: 'POST',
        signal: controller.signal,
        body: JSON.stringify({
          monument_id: monumentId,
          mode_projet: modeProjet,
          travaux_filtres: travauxFiltres,
        }),
      });
      const result = await handleResponse<AideDiagnosticResult>(res);
      useAideStore.getState().setDiagnostic(monumentId, result);
      return result;
    } finally {
      clearTimeout(timeout);
    }
  },

  async getDiagnostics(monumentId: string): Promise<AideDiagnosticResult[]> {
    const res = await authFetch(`${BASE}/aides/diagnostics/${monumentId}`);
    return handleResponse<AideDiagnosticResult[]>(res);
  },

  /** Get filtered aides (from local store cache) */
  getFilteredAides(
    categories: AideCategory[],
    searchQuery: string
  ): Aide[] {
    let filtered = useAideStore.getState().aides;

    if (categories.length > 0) {
      filtered = filtered.filter((a) => categories.includes(a.categorie));
    }

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (a) =>
          a.nom.toLowerCase().includes(q) ||
          a.nomCourt.toLowerCase().includes(q) ||
          a.organisme.toLowerCase().includes(q)
      );
    }

    return filtered;
  },
};
