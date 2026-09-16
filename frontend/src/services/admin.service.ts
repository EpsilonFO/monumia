import type {
  AdminAide,
  ListeUtilisateurs,
  AdminConditionCourante,
  AdminFait,
  ImpactOptions,
  ImpactPredicat,
  InventaireConditions,
  OperateurPredicat,
  OptionSurchargee,
  RoleCompte,
  UtilisateurAdmin,
  StatistiquesCatalogue,
  SurchargeFait,
} from '@/types/admin.types';
import { authFetch, handleResponse } from '@/lib/auth-fetch';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/**
 * Administration du catalogue. Toutes les routes répondent 403 à un compte qui
 * n'est pas administrateur côté serveur (rôle `admin` dans `comptes_roles`, ou
 * socle `ADMIN_USER_IDS`) : `user.estAdmin` ne sert qu'à ne pas proposer une
 * porte fermée, il ne garde rien.
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

  /**
   * Le catalogue en chiffres. Recalculé à chaque appel côté serveur : la page
   * la rappelle d'elle-même, sans rien mettre en cache ici.
   */
  async statistiques(): Promise<StatistiquesCatalogue> {
    const res = await authFetch(`${BASE}/admin/statistiques`);
    return handleResponse<StatistiquesCatalogue>(res);
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

  /**
   * Les comptes et l'état de leurs bascules. Un seul appel au montage : la
   * page filtre ensuite côté client, et chaque bascule se contente de
   * remplacer sa ligne avec ce que l'écriture rend.
   */
  async listUtilisateurs(): Promise<ListeUtilisateurs> {
    const res = await authFetch(`${BASE}/admin/utilisateurs`);
    return handleResponse<ListeUtilisateurs>(res);
  },

  /**
   * Bascule un rôle. Idempotentes toutes les deux — un double-clic ou deux
   * onglets ouverts ne doivent produire ni doublon ni erreur — et chacune rend
   * la LIGNE À JOUR du compte, pas la liste entière.
   */
  async attribuerRole(userId: string, role: RoleCompte): Promise<UtilisateurAdmin> {
    const res = await authFetch(`${BASE}/admin/roles/${role}/${userId}`, { method: 'PUT' });
    return handleResponse<UtilisateurAdmin>(res);
  },

  async retirerRole(userId: string, role: RoleCompte): Promise<UtilisateurAdmin> {
    const res = await authFetch(`${BASE}/admin/roles/${role}/${userId}`, { method: 'DELETE' });
    return handleResponse<UtilisateurAdmin>(res);
  },
};
