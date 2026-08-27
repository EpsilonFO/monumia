import type { AideSuivi, Dossier, Monument, Projet, ProjectDigest } from '@/types';
import { authFetch, handleResponse } from '@/lib/auth-fetch';
import { toMonument } from '@/services/monument.service';
import { toProjet } from '@/services/projet.service';
import { toDossier } from '@/services/dossier.service';
import { toSuivi } from '@/services/suivi.service';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useProjetStore } from '@/stores/useProjetStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useSuiviStore } from '@/stores/useSuiviStore';
import { useAideStore } from '@/stores/useAideStore';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

interface DashboardPayload {
  monuments: Record<string, unknown>[];
  projets: Record<string, unknown>[];
  dossiers: Record<string, unknown>[];
  /** Indexés par id de PROJET. Un monument sans projet n'y figure pas. */
  digests: Record<string, ProjectDigest>;
  /** Indexés par id de PROJET, comme les digests. */
  suivis: Record<string, Record<string, unknown>[]>;
}

export interface DashboardData {
  monuments: Monument[];
  projets: Projet[];
  dossiers: Dossier[];
  digests: Record<string, ProjectDigest>;
  suivis: Record<string, AideSuivi[]>;
}

export const dashboardService = {
  /**
   * Tout ce que les vignettes de monument et de projet affichent, en UN appel.
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
    const projets = payload.projets.map(toProjet);
    const dossiers = payload.dossiers.map(toDossier);
    const suivis = Object.fromEntries(
      Object.entries(payload.suivis).map(([projetId, rows]) => [projetId, rows.map(toSuivi)]),
    );

    useMonumentStore.getState().setMonuments(monuments);
    useProjetStore.getState().setProjets(projets);
    useDossierStore.getState().setDossiers(dossiers);
    useAideStore.getState().setDigests(payload.digests);
    const suiviStore = useSuiviStore.getState();
    for (const [projetId, list] of Object.entries(suivis)) {
      suiviStore.setForProjet(projetId, list);
    }

    return { monuments, projets, dossiers, digests: payload.digests, suivis };
  },
};
