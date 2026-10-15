import type {
  Dossier,
  DossierStep,
  ChecklistItemStatus,
} from '@/types';
import { useDossierStore } from '@/stores/useDossierStore';
import { authFetch, handleResponse } from '@/lib/auth-fetch';
import { suivre } from '@/lib/posthog';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/** Les `GET /dossiers` en vol, par filtre (cf. `fetchAll`). */
const dossiersEnVol = new Map<string, Promise<Dossier[]>>();

// Backend returns snake_case, frontend uses camelCase
export function toDossier(row: Record<string, unknown>): Dossier {
  return {
    id: row.id as string,
    projetId: (row.projet_id ?? row.projetId) as string,
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
    aideFermee: (row.aide_fermee ?? row.aideFermee) as Dossier['aideFermee'],
  };
}

export const dossierService = {
  /**
   * Partagé tant qu'il est en vol : quatre pages l'appellent à leur montage, et
   * le tableau de bord remplit déjà le même store. Deux appels rapprochés
   * rendent la même promesse plutôt que deux requêtes.
   */
  fetchAll(projetId?: string): Promise<Dossier[]> {
    const query = projetId ? `?projet_id=${encodeURIComponent(projetId)}` : '';
    const encours = dossiersEnVol.get(query);
    if (encours) return encours;
    const chargement = (async () => {
      try {
        const res = await authFetch(`${BASE}/dossiers${query}`);
        const rows = await handleResponse<Record<string, unknown>[]>(res);
        const dossiers = rows.map(toDossier);
        useDossierStore.getState().setDossiers(dossiers);
        return dossiers;
      } finally {
        dossiersEnVol.delete(query);
      }
    })();
    dossiersEnVol.set(query, chargement);
    return chargement;
  },

  async getById(id: string): Promise<Dossier> {
    const res = await authFetch(`${BASE}/dossiers/${id}`);
    const row = await handleResponse<Record<string, unknown>>(res);
    return toDossier(row);
  },

  async create(projetId: string, aideId: string, travauxPrevus: string[]): Promise<Dossier> {
    const res = await authFetch(`${BASE}/dossiers`, {
      method: 'POST',
      body: JSON.stringify({
        projet_id: projetId,
        aide_id: aideId,
        travaux_prevus: travauxPrevus,
      }),
    });
    const row = await handleResponse<Record<string, unknown>>(res);
    const dossier = toDossier(row);
    useDossierStore.getState().addDossier(dossier);
    suivre({ nom: 'dossier_cree', proprietes: { aide: aideId } });
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

  async reprendrePieces(dossierId: string): Promise<Dossier> {
    const res = await authFetch(`${BASE}/dossiers/${dossierId}/reprendre-pieces`, {
      method: 'POST',
    });
    const row = await handleResponse<Record<string, unknown>>(res);
    const dossier = toDossier(row);
    useDossierStore.getState().updateDossier(dossierId, dossier);
    return dossier;
  },

  /** Retire le document d'une pièce (rejet d'une reprise). */
  async detacherChecklistItem(dossierId: string, itemId: string): Promise<Dossier> {
    const res = await authFetch(`${BASE}/dossiers/${dossierId}/checklist/${itemId}`, {
      method: 'PATCH',
      body: JSON.stringify({ statut: 'manquant', detacher: true }),
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

  /** Déclare le dossier déposé auprès du financeur ; le serveur fait passer
   *  le suivi de l'aide à « Déposé » dans la foulée. */
  async submit(id: string): Promise<void> {
    const res = await authFetch(`${BASE}/dossiers/${id}/submit`, {
      method: 'POST',
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
    suivre({ nom: 'dossier_depose' });
    const dossier = await this.getById(id);
    useDossierStore.getState().updateDossier(id, dossier);
  },

  /** Annule un dépôt déclaré par erreur : les pièces redeviennent modifiables. */
  async reopen(id: string): Promise<void> {
    const res = await authFetch(`${BASE}/dossiers/${id}/reouverture`, {
      method: 'POST',
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
    const dossier = await this.getById(id);
    useDossierStore.getState().updateDossier(id, dossier);
  },

  /**
   * Télécharge en zip toutes les pièces téléversées du dossier.
   *
   * Le backend construit l'archive (il seul peut lire le bucket privé pour le
   * compte d'un membre) ; on récupère le blob puis on déclenche l'enregistrement
   * via un lien éphémère. `authFetch` est obligatoire : la route est protégée.
   */
  async downloadArchive(id: string, fallbackName = 'dossier'): Promise<void> {
    const res = await authFetch(`${BASE}/dossiers/${id}/archive`);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    // Un séparateur de chemin dans le nom proposé casse l'enregistrement.
    a.download = `${fallbackName.replace(/[/\\]+/g, '-').trim() || 'dossier'}.zip`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
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
