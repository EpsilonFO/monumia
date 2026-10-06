import type { Projet, WorkType } from '@/types';
import { authFetch, handleResponse } from '@/lib/auth-fetch';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/**
 * Ligne `projets` (snake_case, telle que servie par le backend) → `Projet`.
 *
 * Deux subtilités qui méritent le détour :
 *  - `travauxEnvisages` garde son tri-state. La colonne est NOT NULL DEFAULT
 *    '{}' : une liste vide veut donc dire « Pas encore déterminé ». On ne rend
 *    `null` que si la clé est réellement absente de la réponse.
 *  - `questionnaire` est recopié TEL QUEL, clés réservées `_` comprises : elles
 *    repartent au backend à chaque diagnostic, qui les isole lui-même.
 */
export function toProjet(row: Record<string, unknown>): Projet {
  const travaux = row.travaux_envisages ?? row.travauxEnvisages;
  return {
    id: row.id as string,
    monumentId: (row.monument_id ?? row.monumentId) as string,
    userId: (row.user_id ?? row.userId) as string,
    myRole: (row.my_role ?? row.myRole ?? undefined) as Projet['myRole'],
    titre: (row.titre ?? undefined) as string | undefined,
    travauxEnvisages: Array.isArray(travaux) ? (travaux as WorkType[]) : null,
    questionnaire: (row.questionnaire ?? {}) as Projet['questionnaire'],
    clotureAt: (row.cloture_at ?? row.clotureAt ?? undefined) as string | undefined,
    createdAt: (row.created_at ?? row.createdAt ?? new Date().toISOString()) as string,
    updatedAt: (row.updated_at ?? row.updatedAt ?? new Date().toISOString()) as string,
  };
}

export interface ProjetInput {
  titre?: string;
  /** `[]` est une valeur valide (« Pas encore déterminé ») : ne jamais l'élider. */
  travauxEnvisages?: WorkType[];
  questionnaire?: Projet['questionnaire'];
}

/**
 * Réponses DURABLES d'un monument : celles qu'un nouveau projet n'a pas à
 * redemander (faits de scope `monument` ou `proprietaire`).
 *
 * `source` dit de quel projet vient chaque réponse et `titres` comment il
 * s'appelle : le wizard en fait un bandeau, et une reprise qu'on ne peut pas
 * tracer n'est pas explicable.
 */
export interface RepriseDurable {
  fact: string;
  /** La question telle que le questionnaire l'aurait posée. */
  question: string;
  /** La réponse en clair, ou `null` quand on ne sait pas la nommer (tranche
   *  numérique, fabriquée par le moteur depuis les seuils des aides). */
  reponse: string | null;
  /** Le bien ou le porteur : l'écran de reprise range ses lignes par bloc. */
  scope?: 'monument' | 'proprietaire';
  projetId: string;
  projetTitre: string | null;
}

export interface FaitsDurables {
  reponses: Projet['questionnaire'];
  source: Record<string, string>;
  titres: Record<string, string | null>;
  /** De quoi NOMMER les reprises à l'écran. Indispensable : une réponse reprise
   *  n'est plus une incertitude, donc le moteur ne rend plus sa question, donc
   *  aucune fiche d'aide ne l'offre à la correction. */
  details: RepriseDurable[];
}

export const projetService = {
  async faitsDurables(monumentId: string): Promise<FaitsDurables> {
    const res = await authFetch(`${BASE}/monuments/${monumentId}/faits-durables`);
    return handleResponse<FaitsDurables>(res);
  },

  async listByMonument(monumentId: string): Promise<Projet[]> {
    const res = await authFetch(`${BASE}/monuments/${monumentId}/projets`);
    const rows = await handleResponse<Record<string, unknown>[]>(res);
    return rows.map(toProjet);
  },

  async create(monumentId: string, input: ProjetInput = {}): Promise<Projet> {
    const res = await authFetch(`${BASE}/monuments/${monumentId}/projets`, {
      method: 'POST',
      body: JSON.stringify(input),
    });
    return toProjet(await handleResponse<Record<string, unknown>>(res));
  },

  async getById(id: string): Promise<Projet> {
    const res = await authFetch(`${BASE}/projets/${id}`);
    return toProjet(await handleResponse<Record<string, unknown>>(res));
  },

  async update(id: string, input: ProjetInput): Promise<Projet> {
    const res = await authFetch(`${BASE}/projets/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(input),
    });
    return toProjet(await handleResponse<Record<string, unknown>>(res));
  },

  async delete(id: string): Promise<void> {
    const res = await authFetch(`${BASE}/projets/${id}`, { method: 'DELETE' });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
  },
};
