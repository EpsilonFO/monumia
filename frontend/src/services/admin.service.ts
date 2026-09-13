import type {
  AdminAide,
  AdminConditionCourante,
  AdminFait,
  ImpactOptions,
  ImpactPredicat,
  InventaireConditions,
  OperateurPredicat,
  OptionSurchargee,
  SurchargeFait,
} from '@/types/admin.types';
import { authFetch, handleResponse } from '@/lib/auth-fetch';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/**
 * Administration du catalogue. Toutes les routes répondent 403 à un compte qui
 * n'est pas dans `ADMIN_USER_IDS` côté serveur : `user.estAdmin` ne sert qu'à
 * ne pas proposer une porte fermée, il ne garde rien.
 *
 * Chaque écriture rend la LIGNE À JOUR (aide ou fait complet) : la page
 * remplace la sienne avec, sans relister tout le catalogue.
 */
export const adminService = {
  async listAides(): Promise<AdminAide[]> {
    const res = await authFetch(`${BASE}/admin/aides`);
    return handleResponse<AdminAide[]>(res);
  },

  async retirerAide(slug: string, motif?: string | null): Promise<AdminAide> {
    const res = await authFetch(`${BASE}/admin/aides/${slug}/retrait`, {
      method: 'PUT',
      body: JSON.stringify({ motif: motif ?? null }),
    });
    return handleResponse<AdminAide>(res);
  },

  async republierAide(slug: string): Promise<AdminAide> {
    const res = await authFetch(`${BASE}/admin/aides/${slug}/retrait`, { method: 'DELETE' });
    return handleResponse<AdminAide>(res);
  },

  async listFaits(): Promise<AdminFait[]> {
    const res = await authFetch(`${BASE}/admin/faits`);
    return handleResponse<AdminFait[]>(res);
  },

  /** L'impact d'un brouillon de réponses, sans rien écrire. */
  async simulerOptions(key: string, options: OptionSurchargee[]): Promise<ImpactOptions> {
    const res = await authFetch(`${BASE}/admin/faits/${key}/simuler`, {
      method: 'POST',
      body: JSON.stringify({ options }),
    });
    return handleResponse<ImpactOptions>(res);
  },

  async surchargerFait(key: string, surcharge: SurchargeFait): Promise<AdminFait> {
    const res = await authFetch(`${BASE}/admin/faits/${key}`, {
      method: 'PUT',
      body: JSON.stringify(surcharge),
    });
    return handleResponse<AdminFait>(res);
  },

  async retablirFait(key: string): Promise<AdminFait> {
    const res = await authFetch(`${BASE}/admin/faits/${key}`, { method: 'DELETE' });
    return handleResponse<AdminFait>(res);
  },

  async listConditions(): Promise<InventaireConditions> {
    const res = await authFetch(`${BASE}/admin/conditions`);
    return handleResponse<InventaireConditions>(res);
  },

  /**
   * L'impact d'un prédicat, sans rien écrire.
   *
   * Le corps porte un OPÉRATEUR et des VALEURS, jamais un prédicat JSON brut :
   * c'est le type qui rend inexprimable la moitié des états invalides, pas la
   * bonne volonté du composant.
   */
  async simulerPredicat(
    slug: string,
    conditionId: string,
    operateur: OperateurPredicat,
    valeurs: string[],
  ): Promise<ImpactPredicat> {
    const res = await authFetch(`${BASE}/admin/conditions/${slug}/${conditionId}/simuler`, {
      method: 'POST',
      body: JSON.stringify({ operateur, valeurs }),
    });
    return handleResponse<ImpactPredicat>(res);
  },

  async surchargerPredicat(
    slug: string,
    conditionId: string,
    operateur: OperateurPredicat,
    valeurs: string[],
    motif?: string | null,
  ): Promise<AdminConditionCourante> {
    const res = await authFetch(`${BASE}/admin/conditions/${slug}/${conditionId}`, {
      method: 'PUT',
      body: JSON.stringify({ operateur, valeurs, motif: motif ?? null }),
    });
    return handleResponse<AdminConditionCourante>(res);
  },

  async retablirPredicat(slug: string, conditionId: string): Promise<AdminConditionCourante> {
    const res = await authFetch(`${BASE}/admin/conditions/${slug}/${conditionId}`, {
      method: 'DELETE',
    });
    return handleResponse<AdminConditionCourante>(res);
  },
};
