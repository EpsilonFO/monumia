import type { Aide, AideDiagnosticResult, ProjectQuestionnaireAnswers } from '@/types';
import { authFetch, handleResponse } from '@/lib/auth-fetch';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export const aideService = {
  async getById(id: string): Promise<Aide> {
    const res = await authFetch(`${BASE}/aides/${id}`);
    return handleResponse<Aide>(res);
  },

  /**
   * Diagnostic déterministe, restreint aux aides « engine-ready » (conditions
   * entièrement typées). Non persisté côté serveur : le résultat n'a pas d'`id`
   * et le QCM se résout côté client via eliminationsParOption.
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

  /**
   * Diagnostic d'un projet, prêt à afficher. Le moteur est ré-évalué AVEC les
   * réponses enregistrées du monument (`questionnaire`) : un `user_fact` répondu
   * positivement promeut l'aide en éligible, un répondu négativement la
   * rétrograde — ce qu'une simple élimination côté client ne permettait pas.
   * Source unique : wizard, page projet, liste et dashboard.
   *
   * `answers` est le `questionnaire` du monument tel quel : réponses aux faits
   * et clés réservées (`_raisons`, les intentions de projet) mêlées — le
   * backend les sépare.
   */
  async runProjectDiagnostic(
    monumentId: string,
    answers?: ProjectQuestionnaireAnswers,
  ): Promise<AideDiagnosticResult> {
    return this.runDeterministicDiagnostic(monumentId, answers ?? {});
  },
};
