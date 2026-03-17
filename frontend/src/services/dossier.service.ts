import type {
  Dossier,
  DossierStep,
  ChecklistItemStatus,
} from '@/types';
import { useDossierStore } from '@/stores/useDossierStore';
import { authFetch, handleResponse } from '@/lib/auth-fetch';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

// Backend returns snake_case, frontend uses camelCase
function toDossier(row: Record<string, unknown>): Dossier {
  return {
    id: row.id as string,
    monumentId: (row.monument_id ?? row.monumentId) as string,
    aideId: (row.aide_id ?? row.aideId) as string,
    userId: (row.user_id ?? row.userId) as string,
    titre: row.titre as string,
    description: row.description as string | undefined,
    etapeActuelle: (row.etape_actuelle ?? row.etapeActuelle) as Dossier['etapeActuelle'],
    statut: row.statut as Dossier['statut'],
    progressionPourcentage: (row.progression_pourcentage ?? row.progressionPourcentage ?? 0) as number,
    travauxPrevus: (row.travaux_prevus ?? row.travauxPrevus ?? []) as Dossier['travauxPrevus'],
    montantEstime: (row.montant_estime ?? row.montantEstime) as number | undefined,
    checklist: (row.checklist ?? []) as Dossier['checklist'],
    sections: (row.sections ?? []) as Dossier['sections'],
    echeances: (row.echeances ?? []) as Dossier['echeances'],
    collaborateurs: (row.collaborateurs ?? []) as Dossier['collaborateurs'],
    dateCreation: (row.date_creation ?? row.dateCreation ?? new Date().toISOString()) as string,
    dateDerniereModification: (row.date_derniere_modification ?? row.dateDerniereModification ?? new Date().toISOString()) as string,
    dateSoumission: (row.date_soumission ?? row.dateSoumission) as string | undefined,
  };
}

export const dossierService = {
  async fetchAll(): Promise<Dossier[]> {
    const res = await authFetch(`${BASE}/dossiers`);
    const rows = await handleResponse<Record<string, unknown>[]>(res);
    const dossiers = rows.map(toDossier);
    useDossierStore.getState().setDossiers(dossiers);
    return dossiers;
  },

  async getById(id: string): Promise<Dossier> {
    const res = await authFetch(`${BASE}/dossiers/${id}`);
    const row = await handleResponse<Record<string, unknown>>(res);
    return toDossier(row);
  },

  async create(monumentId: string, aideId: string, travauxPrevus: string[]): Promise<Dossier> {
    const res = await authFetch(`${BASE}/dossiers`, {
      method: 'POST',
      body: JSON.stringify({
        monument_id: monumentId,
        aide_id: aideId,
        travaux_prevus: travauxPrevus,
      }),
    });
    const row = await handleResponse<Record<string, unknown>>(res);
    const dossier = toDossier(row);
    useDossierStore.getState().addDossier(dossier);
    return dossier;
  },

  async update(id: string, updates: { titre?: string; description?: string; statut?: string; etape_actuelle?: number; progression_pourcentage?: number; montant_estime?: number; date_soumission?: string }): Promise<Dossier> {
    const res = await authFetch(`${BASE}/dossiers/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
    const row = await handleResponse<Record<string, unknown>>(res);
    const dossier = toDossier(row);
    useDossierStore.getState().updateDossier(id, dossier);
    return dossier;
  },

  async updateStep(id: string, step: DossierStep): Promise<Dossier> {
    const statusMap: Record<DossierStep, string> = {
      1: 'brouillon',
      2: 'en_cours',
      3: 'en_cours',
      4: 'complet',
      5: 'soumis',
    };
    return this.update(id, {
      etape_actuelle: step,
      statut: statusMap[step],
    });
  },

  async updateChecklistItem(dossierId: string, itemId: string, statut: ChecklistItemStatus, documentId?: string): Promise<Dossier> {
    const res = await authFetch(`${BASE}/dossiers/${dossierId}/checklist/${itemId}`, {
      method: 'PATCH',
      body: JSON.stringify({
        statut,
        ...(documentId !== undefined ? { document_id: documentId } : {}),
      }),
    });
    const row = await handleResponse<Record<string, unknown>>(res);
    const dossier = toDossier(row);
    useDossierStore.getState().updateDossier(dossierId, dossier);
    return dossier;
  },

  async updateSection(dossierId: string, sectionId: string, contenu: string): Promise<Dossier> {
    const res = await authFetch(`${BASE}/dossiers/${dossierId}/sections/${sectionId}`, {
      method: 'PATCH',
      body: JSON.stringify({ contenu }),
    });
    const row = await handleResponse<Record<string, unknown>>(res);
    const dossier = toDossier(row);
    useDossierStore.getState().updateDossier(dossierId, dossier);
    return dossier;
  },

  async addCollaborateur(dossierId: string, collab: { email: string; nom: string; role: string; permissions: string }): Promise<void> {
    await authFetch(`${BASE}/dossiers/${dossierId}/collaborateurs`, {
      method: 'POST',
      body: JSON.stringify(collab),
    });
    // Refresh the full dossier to get updated collaborateurs list
    const dossier = await this.getById(dossierId);
    useDossierStore.getState().updateDossier(dossierId, dossier);
  },

  async removeCollaborateur(dossierId: string, collabId: string): Promise<void> {
    const res = await authFetch(`${BASE}/dossiers/${dossierId}/collaborateurs/${collabId}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
    const dossier = await this.getById(dossierId);
    useDossierStore.getState().updateDossier(dossierId, dossier);
  },

  async addEcheance(dossierId: string, echeance: { label: string; date: string; type: string }): Promise<void> {
    await authFetch(`${BASE}/dossiers/${dossierId}/echeances`, {
      method: 'POST',
      body: JSON.stringify(echeance),
    });
    const dossier = await this.getById(dossierId);
    useDossierStore.getState().updateDossier(dossierId, dossier);
  },

  async toggleEcheance(dossierId: string, echeanceId: string): Promise<void> {
    const res = await authFetch(`${BASE}/dossiers/${dossierId}/echeances/${echeanceId}/toggle`, {
      method: 'PATCH',
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
    const dossier = await this.getById(dossierId);
    useDossierStore.getState().updateDossier(dossierId, dossier);
  },

  async submit(id: string): Promise<void> {
    const res = await authFetch(`${BASE}/dossiers/${id}/submit`, {
      method: 'POST',
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
    const dossier = await this.getById(id);
    useDossierStore.getState().updateDossier(id, dossier);
  },

  async delete(id: string): Promise<void> {
    const res = await authFetch(`${BASE}/dossiers/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
    useDossierStore.getState().deleteDossier(id);
  },
};
