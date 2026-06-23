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
    travauxFiltres?: WorkType[],
    options?: { skipQcm?: boolean }
  ): Promise<AideDiagnosticResult> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 360_000); // 6 min — ≥ backend QCM timeout (300s + retries)
    try {
      const res = await authFetch(`${BASE}/aides/diagnostic`, {
        method: 'POST',
        signal: controller.signal,
        body: JSON.stringify({
          monument_id: monumentId,
          mode_projet: modeProjet,
          travaux_filtres: travauxFiltres,
          skip_qcm: options?.skipQcm ?? false,
        }),
      });
      return handleResponse<AideDiagnosticResult>(res);
    } finally {
      clearTimeout(timeout);
    }
  },

  /**
   * Diagnostic 100 % déterministe (aucun LLM), restreint aux aides « engine-ready »
   * (conditions entièrement typées). Non persisté côté serveur : le résultat n'a
   * pas d'`id` et le QCM se résout côté client via eliminationsParOption.
   */
  async runDeterministicDiagnostic(
    monumentId: string,
    answers?: Record<string, unknown>
  ): Promise<AideDiagnosticResult> {
    const res = await authFetch(`${BASE}/aides/diagnostic-deterministe`, {
      method: 'POST',
      body: JSON.stringify({ monument_id: monumentId, answers }),
    });
    return handleResponse<AideDiagnosticResult>(res);
  },

  async getDiagnostics(monumentId: string): Promise<AideDiagnosticResult[]> {
    const res = await authFetch(`${BASE}/aides/diagnostics/${monumentId}`);
    return handleResponse<AideDiagnosticResult[]>(res);
  },

  /**
   * Diagnostic d'un projet, prêt à afficher. Le moteur déterministe est ré-évalué
   * AVEC les réponses enregistrées du monument (`questionnaire`) : un `user_fact`
   * répondu positivement promeut l'aide en éligible, un répondu négativement la
   * rétrograde — ce qu'une simple élimination côté client ne permettait pas.
   * Source unique : wizard, page projet, liste et dashboard.
   */
  async runProjectDiagnostic(
    monumentId: string,
    answers?: Record<string, string>,
  ): Promise<AideDiagnosticResult> {
    return this.runDeterministicDiagnostic(monumentId, answers ?? {});
  },

  async saveQcmAnswers(
    diagnosticId: string,
    qcmAnswers: Record<string, string>,
  ): Promise<void> {
    const res = await authFetch(
      `${BASE}/aides/diagnostics/by-id/${diagnosticId}/qcm-answers`,
      {
        method: 'PATCH',
        body: JSON.stringify({ qcm_answers: qcmAnswers }),
      },
    );
    await handleResponse(res);
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
