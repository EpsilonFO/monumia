import type {
  Aide,
  AideDiagnosticResult,
  DiagnosticInviteResult,
  MonumentInput,
  ProjectQuestionnaireAnswers,
  WorkType,
} from '@/types';
import { authFetch, handleResponse } from '@/lib/auth-fetch';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export const aideService = {
  async getById(id: string): Promise<Aide> {
    const res = await authFetch(`${BASE}/aides/${id}`);
    return handleResponse<Aide>(res);
  },

  /** Le panneau d'une aide fermée a été lu : ses dossiers en préparation ne
   *  reviendront plus pour ce compte. */
  async marquerFermeeVue(slug: string): Promise<void> {
    const res = await authFetch(`${BASE}/aides/${encodeURIComponent(slug)}/fermee-vue`, {
      method: 'POST',
    });
    if (!res.ok) await handleResponse(res);
  },

  /**
   * Diagnostic déterministe d'un PROJET de travaux, restreint aux aides
   * « engine-ready » (conditions entièrement typées). Non persisté côté serveur :
   * le résultat n'a pas d'`id` et le QCM se résout côté client via
   * eliminationsParOption.
   *
   * Le cadrage (travaux envisagés) est relu SUR LE SERVEUR depuis le projet :
   * il faut donc l'avoir persisté (POST/PATCH) avant d'appeler, sinon le
   * diagnostic porte sur l'état précédent sans que rien ne le signale.
   */
  async runDeterministicDiagnostic(
    projetId: string,
    answers?: Record<string, unknown>
  ): Promise<AideDiagnosticResult> {
    const res = await authFetch(`${BASE}/aides/diagnostic-deterministe`, {
      method: 'POST',
      body: JSON.stringify({ projet_id: projetId, answers }),
    });
    return handleResponse<AideDiagnosticResult>(res);
  },

  /**
   * Diagnostic d'un projet, prêt à afficher. Le moteur est ré-évalué AVEC les
   * réponses enregistrées du projet (`questionnaire`) : un `user_fact` répondu
   * positivement promeut l'aide en éligible, un répondu négativement la
   * rétrograde — ce qu'une simple élimination côté client ne permettait pas.
   * Source unique : wizard, page projet, liste et dashboard.
   *
   * `answers` est le `questionnaire` du projet tel quel : réponses aux faits
   * et clés réservées (`_raisons`, les intentions de projet) mêlées — le
   * backend les sépare.
   */
  async runProjectDiagnostic(
    projetId: string,
    answers?: ProjectQuestionnaireAnswers,
  ): Promise<AideDiagnosticResult> {
    return this.runDeterministicDiagnostic(projetId, answers ?? {});
  },

  /**
   * Le même diagnostic, sur le questionnaire ENREGISTRÉ du projet, que le
   * serveur relit lui-même (`answers` absent du corps, cf. routers/aides.py).
   * Sert à partir avant d'avoir le projet en main : la page d'un projet n'a
   * plus à attendre `GET /projets/{id}` pour lancer le plus lourd de ses appels.
   * Le résultat porte les réponses utilisées dans `qcmAnswers`.
   */
  async runProjectDiagnosticEnregistre(projetId: string): Promise<AideDiagnosticResult> {
    return this.runDeterministicDiagnostic(projetId, undefined);
  },

  /**
   * Diagnostic d'un monument DÉCRIT SUR PLACE, sans compte : le parcours
   * découverte, de la landing à l'inscription.
   *
   * Tout part dans le corps — le bien, le cadrage, les réponses — parce que
   * rien n'existe en base : ni monument, ni projet. Le brouillon vit dans le
   * `localStorage` (cf. `useBrouillonInviteStore`) et l'inscription le rejoue.
   *
   * `fetch` nu, comme `auth.service` : l'endpoint est public, et passer par
   * `authFetch` déclencherait un rafraîchissement de jeton inutile.
   *
   * La réponse ne porte AUCUNE aide : les questions du QCM (identifiants
   * pseudonymisés) et une synthèse chiffrée.
   */
  async runDiagnosticInvite(input: {
    monument: MonumentInput;
    travauxEnvisages: WorkType[];
    answers: ProjectQuestionnaireAnswers;
  }): Promise<DiagnosticInviteResult> {
    const res = await fetch(`${BASE}/aides/diagnostic-invite`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    });
    return handleResponse<DiagnosticInviteResult>(res);
  },
};
