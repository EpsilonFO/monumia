import type { AideSuivi, Dossier, Monument, ProjectDigest } from '@/types';
import { authFetch, handleResponse } from '@/lib/auth-fetch';
import { toMonument } from '@/services/monument.service';
import { toDossier } from '@/services/dossier.service';
import { toSuivi } from '@/services/suivi.service';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useSuiviStore } from '@/stores/useSuiviStore';
import { useAideStore } from '@/stores/useAideStore';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

interface DashboardPayload {
  monuments: Record<string, unknown>[];
  dossiers: Record<string, unknown>[];
  digests: Record<string, ProjectDigest>;
  suivis: Record<string, Record<string, unknown>[]>;
}

export interface DashboardData {
  monuments: Monument[];
  dossiers: Dossier[];
  digests: Record<string, ProjectDigest>;
  suivis: Record<string, AideSuivi[]>;
}

export const dashboardService = {
  /**
   * Tout ce que les vignettes de projet affichent, en UN appel.
   *
   * Remplace la cascade d'origine (`/monuments`, `/dossiers`, puis un
   * diagnostic et une liste de suivis par projet) : chaque requête repayait la
   * vérification du token, et les diagnostics complets pesaient ~1,7 Mo pièce.
   * Les stores sont garnis ici, comme le faisaient les services individuels.
   */
  async load(): Promise<DashboardData> {
    const res = await authFetch(`${BASE}/dashboard`);
    const payload = await handleResponse<DashboardPayload>(res);

    const monuments = payload.monuments.map(toMonument);
    const dossiers = payload.dossiers.map(toDossier);
    const suivis = Object.fromEntries(
      Object.entries(payload.suivis).map(([monumentId, rows]) => [monumentId, rows.map(toSuivi)]),
    );

    useMonumentStore.getState().setMonuments(monuments);
    useDossierStore.getState().setDossiers(dossiers);
    useAideStore.getState().setDigests(payload.digests);
    const suiviStore = useSuiviStore.getState();
    for (const [monumentId, list] of Object.entries(suivis)) {
      suiviStore.setForMonument(monumentId, list);
    }

    return { monuments, dossiers, digests: payload.digests, suivis };
  },
};
