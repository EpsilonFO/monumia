import type { Monument, MonumentInput, MonumentPhoto } from '@/types';
import { authFetch, handleResponse } from '@/lib/auth-fetch';
import { uploadToStorage } from '@/lib/storage-upload';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/**
 * Ligne `monuments` (snake_case) → `Monument`.
 *
 * Ne mappe QUE des colonnes réelles. Dix attributs (affectataire, superficie,
 * matériaux, couverture, urgence, diagnostic réalisé…) ont été droppés par la
 * migration 20260516174303, et le cadrage de chantier (questionnaire,
 * travaux_envisages, cloture_at) est parti sur la table `projets` : les
 * chercher ici ne rendrait jamais rien.
 */
/** Ligne photo (snake_case côté API) → `MonumentPhoto`. */
function toPhoto(row: Record<string, unknown>): MonumentPhoto {
  return {
    id: row.id as string,
    url: row.url as string,
    signedUrl: (row.signed_url ?? row.signedUrl) as string | undefined,
    legende: (row.legende as string) ?? '',
    type: row.type as MonumentPhoto['type'],
    datePhoto: (row.datePhoto ?? row.date_photo) as string | undefined,
  };
}

/**
 * `monuments.type_edifice` est un `text[]` ; une chaîne seule (colonne d'avant
 * la migration 20260930082523) vaut un type, un tableau vide aucun.
 */
function typesDeLaLigne(brut: unknown): Monument['typeEdifice'] {
  if (typeof brut === 'string') return [brut] as Monument['typeEdifice'];
  return Array.isArray(brut) && brut.length > 0 ? (brut as Monument['typeEdifice']) : undefined;
}

/**
 * `monuments.proprietaire` est un `ownership_type[]` ; une chaîne seule (colonne
 * d'avant la migration 20260930084241) vaut un propriétaire.
 */
function proprietairesDeLaLigne(brut: unknown): Monument['proprietaire'] {
  if (typeof brut === 'string') return [brut] as Monument['proprietaire'];
  return Array.isArray(brut) ? (brut as Monument['proprietaire']) : [];
}

export function toMonument(row: Record<string, unknown>): Monument {
  return {
    id: row.id as string,
    userId: row.user_id as string,
    myRole: (row.my_role as Monument['myRole']) ?? undefined,
    members: Array.isArray(row.members)
      ? (row.members as Array<Record<string, unknown>>).map((mm) => ({
          userId: mm.user_id as string,
          prenom: (mm.prenom as string) ?? '',
          nom: (mm.nom as string) ?? '',
          role: mm.role as import('@/types').ProjectRole,
        }))
      : undefined,
    memberCount: (row.member_count as number) ?? undefined,
    // L'offre qui gouverne ce bien, résolue par le serveur. Absente d'un
    // monument fabriqué localement : les hooks retombent alors sur le gratuit.
    offre: (row.offre as Monument['offre']) ?? undefined,
    nom: row.nom as string,
    commune: row.commune as string,
    codeInsee: row.code_insee as string ?? row.codeInsee as string ?? '',
    departement: row.departement as string,
    region: row.region as Monument['region'],
    referenceMerimee: row.reference_merimee as string ?? row.referenceMerimee as string,
    protection: row.protection as Monument['protection'],
    dateProtection: row.date_protection as string ?? row.dateProtection as string,
    typeProtection: row.type_protection as string ?? row.typeProtection as string,
    proprietaire: proprietairesDeLaLigne(row.proprietaire),
    siecleConstruction: row.siecle_construction as string ?? row.siecleConstruction as string,
    descriptionGenerale: row.description_generale as string ?? row.descriptionGenerale as string,
    typeEdifice: typesDeLaLigne(row.type_edifice ?? row.typeEdifice),
    affecteAuCulte: (row.affecte_au_culte ?? row.affecteAuCulte ?? undefined) as Monument['affecteAuCulte'],
    architectureRomane: (row.architecture_romane ?? row.architectureRomane ?? undefined) as Monument['architectureRomane'],
    merimeeDomaine: (row.merimee_domaine ?? row.merimeeDomaine ?? undefined) as Monument['merimeeDomaine'],
    etatConservation: (row.etat_conservation ?? row.etatConservation ?? undefined) as Monument['etatConservation'],
    photos: Array.isArray(row.photos)
      ? (row.photos as Array<Record<string, unknown>>).map(toPhoto)
      : [],
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

  async create(data: MonumentInput): Promise<Monument> {
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

  /**
   * Dépose une nouvelle photo de profil : le fichier part dans le bucket privé
   * sous le dossier de l'utilisateur, puis le backend l'installe sur le
   * monument (et efface l'ancienne). Rend la photo, lien signé compris.
   */
  async setPhotoProfil(monumentId: string, file: File, userId: string): Promise<MonumentPhoto> {
    const url = await uploadToStorage(file, userId);
    const res = await authFetch(`${BASE}/monuments/${monumentId}/photo-profil`, {
      method: 'PUT',
      body: JSON.stringify({ url, legende: '' }),
    });
    const row = await handleResponse<Record<string, unknown>>(res);
    return toPhoto(row);
  },

  async removePhotoProfil(monumentId: string): Promise<void> {
    const res = await authFetch(`${BASE}/monuments/${monumentId}/photo-profil`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
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
