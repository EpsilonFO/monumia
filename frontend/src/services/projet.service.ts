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

export const projetService = {
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
