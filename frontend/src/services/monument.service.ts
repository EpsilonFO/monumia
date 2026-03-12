import type { Monument, MonumentPhoto } from '@/types';
import { authFetch, handleResponse } from '@/lib/auth-fetch';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

// The backend returns snake_case keys directly as stored in DB.
// The Monument type uses camelCase. We need a mapping layer.
function toMonument(row: Record<string, unknown>): Monument {
  return {
    id: row.id as string,
    userId: row.user_id as string,
    nom: row.nom as string,
    denomination: row.denomination as string,
    codePostal: (row.code_postal as string) ?? (row.codePostal as string) ?? '',
    commune: row.commune as string,
    codeInsee: row.code_insee as string ?? row.codeInsee as string ?? '',
    departement: row.departement as string,
    region: row.region as Monument['region'],
    referenceMerimee: row.reference_merimee as string ?? row.referenceMerimee as string,
    coordonnees: row.coordonnees as Monument['coordonnees'],
    protection: row.protection as Monument['protection'],
    dateProtection: row.date_protection as string ?? row.dateProtection as string,
    typeProtection: row.type_protection as string ?? row.typeProtection as string,
    proprietaire: row.proprietaire as Monument['proprietaire'],
    affectataire: row.affectataire as string,
    siecleConstruction: row.siecle_construction as string ?? row.siecleConstruction as string,
    periodeConstruction: row.periode_construction as string[] ?? row.periodeConstruction as string[],
    superficie: row.superficie as number,
    materiaux: row.materiaux as string[],
    typeCouverture: row.type_couverture as string ?? row.typeCouverture as string,
    nombreNiveaux: row.nombre_niveaux as number ?? row.nombreNiveaux as number,
    descriptionGenerale: row.description_generale as string ?? row.descriptionGenerale as string,
    etatConservation: row.etat_conservation as Monument['etatConservation'] ?? row.etatConservation as Monument['etatConservation'],
    travauxEnvisages: row.travaux_envisages as Monument['travauxEnvisages'] ?? row.travauxEnvisages as Monument['travauxEnvisages'],
    urgenceTravaux: row.urgence_travaux as Monument['urgenceTravaux'] ?? row.urgenceTravaux as Monument['urgenceTravaux'],
    diagnosticRealise: row.diagnostic_realise as boolean ?? row.diagnosticRealise as boolean,
    derniersTravaux: row.derniers_travaux as string ?? row.derniersTravaux as string,
    descriptionEtat: row.description_etat as string ?? row.descriptionEtat as string,
    photos: (row.photos as MonumentPhoto[]) ?? [],
    completionPercentage: row.completion_percentage as number ?? row.completionPercentage as number ?? 0,
    createdAt: row.created_at as string ?? row.createdAt as string ?? new Date().toISOString(),
    updatedAt: row.updated_at as string ?? row.updatedAt as string ?? new Date().toISOString(),
  };
}

export const monumentService = {
  async getAll(): Promise<Monument[]> {
    const res = await authFetch(`${BASE}/monuments`);
    const rows = await handleResponse<Record<string, unknown>[]>(res);
    return rows.map(toMonument);
  },

  async getById(id: string): Promise<Monument> {
    const res = await authFetch(`${BASE}/monuments/${id}`);
    const row = await handleResponse<Record<string, unknown>>(res);
    return toMonument(row);
  },

  async create(data: Omit<Monument, 'id' | 'userId' | 'createdAt' | 'updatedAt' | 'completionPercentage' | 'photos'>): Promise<Monument> {
    const res = await authFetch(`${BASE}/monuments`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
    const row = await handleResponse<Record<string, unknown>>(res);
    return toMonument(row);
  },

  async update(id: string, updates: Partial<Monument>): Promise<Monument> {
    const res = await authFetch(`${BASE}/monuments/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
    const row = await handleResponse<Record<string, unknown>>(res);
    return toMonument(row);
  },

  async delete(id: string): Promise<void> {
    const res = await authFetch(`${BASE}/monuments/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
  },

  async addPhoto(monumentId: string, photo: Omit<MonumentPhoto, 'id'>): Promise<MonumentPhoto> {
    const res = await authFetch(`${BASE}/monuments/${monumentId}/photos`, {
      method: 'POST',
      body: JSON.stringify(photo),
    });
    return handleResponse<MonumentPhoto>(res);
  },

  async removePhoto(monumentId: string, photoId: string): Promise<void> {
    const res = await authFetch(`${BASE}/monuments/${monumentId}/photos/${photoId}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
  },
};
