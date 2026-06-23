import type { AideSuivi, AideSuiviStatut, AideRefusMotif } from '@/types';
import { useSuiviStore } from '@/stores/useSuiviStore';
import { authFetch, handleResponse } from '@/lib/auth-fetch';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

// Backend renvoie du snake_case, le frontend utilise du camelCase.
function toSuivi(row: Record<string, unknown>): AideSuivi {
  return {
    id: row.id as string,
    monumentId: (row.monument_id ?? row.monumentId) as string,
    aideId: (row.aide_id ?? row.aideId) as string,
    userId: (row.user_id ?? row.userId) as string,
    statut: (row.statut ?? 'a_faire') as AideSuiviStatut,
    montantObtenu: (row.montant_obtenu ?? row.montantObtenu) as number | undefined,
    motifRefusCode: (row.motif_refus_code ?? row.motifRefusCode) as
      | AideRefusMotif
      | undefined,
    motifRefusDetail: (row.motif_refus_detail ?? row.motifRefusDetail) as
      | string
      | undefined,
    note: (row.note ?? undefined) as string | undefined,
    historique: (row.historique ?? []) as AideSuivi['historique'],
    createdAt: (row.created_at ?? row.createdAt ?? new Date().toISOString()) as string,
    updatedAt: (row.updated_at ?? row.updatedAt ?? new Date().toISOString()) as string,
  };
}

export interface UpsertSuiviInput {
  statut: AideSuiviStatut;
  montantObtenu?: number;
  motifRefusCode?: AideRefusMotif;
  motifRefusDetail?: string;
  note?: string;
}

export const suiviService = {
  async fetchByMonument(monumentId: string): Promise<AideSuivi[]> {
    const res = await authFetch(`${BASE}/monuments/${monumentId}/aide-suivis`);
    const rows = await handleResponse<Record<string, unknown>[]>(res);
    const suivis = rows.map(toSuivi);
    useSuiviStore.getState().setForMonument(monumentId, suivis);
    return suivis;
  },

  async upsert(
    monumentId: string,
    aideId: string,
    input: UpsertSuiviInput
  ): Promise<AideSuivi> {
    const res = await authFetch(
      `${BASE}/monuments/${monumentId}/aides/${aideId}/suivi`,
      {
        method: 'PUT',
        body: JSON.stringify({
          statut: input.statut,
          montant_obtenu: input.montantObtenu ?? null,
          motif_refus_code: input.motifRefusCode ?? null,
          motif_refus_detail: input.motifRefusDetail ?? null,
          note: input.note ?? null,
        }),
      }
    );
    const row = await handleResponse<Record<string, unknown>>(res);
    const suivi = toSuivi(row);
    useSuiviStore.getState().upsert(suivi);
    return suivi;
  },

  async remove(monumentId: string, aideId: string): Promise<void> {
    const res = await authFetch(
      `${BASE}/monuments/${monumentId}/aides/${aideId}/suivi`,
      { method: 'DELETE' }
    );
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
    useSuiviStore.getState().remove(monumentId, aideId);
  },
};
