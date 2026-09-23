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

/** Le `GET /dashboard` en vol, partagé par tous les appelants (cf. `load`). */
let enVol: Promise<DashboardData> | null = null;

export const dashboardService = {
  /**
   * Tout ce que les vignettes de monument et de projet affichent, en UN appel.
   *
   * Remplace la cascade d'origine (`/monuments`, `/dossiers`, puis un
   * diagnostic et une liste de suivis par projet) : chaque requête repayait la
   * vérification du token, et les diagnostics complets pesaient ~1,7 Mo pièce.
   * Les stores sont garnis ici, comme le faisaient les services individuels.
   *
   * Partagé tant qu'il est en vol : la coquille de l'espace et les pages qui
   * attendent la réponse l'appellent chacune à leur montage, et deux requêtes
   * parties ensemble se seraient disputé les stores.
   */
  load(): Promise<DashboardData> {
    if (!enVol) {
      enVol = charger().finally(() => {
        enVol = null;
      });
    }
    return enVol;
  },
};

/**
 * Un projet écrit PENDANT que la requête était en vol (une réponse au
 * questionnaire, un renommage) est plus récent que la ligne qu'elle rapporte :
 * l'écraser ferait revenir la page sur l'état d'avant, et relancer le
 * diagnostic sur d'anciennes réponses. La requête part de la coquille au
 * démarrage, en même temps que la page du projet : la course n'a rien de
 * théorique. Un projet relu du cache, lui, cède toujours la place.
 */
function garderLesPlusRecents(projets: Projet[]): Projet[] {
  const actuels = new Map(
    useProjetStore
      .getState()
      .projets.filter((p) => !p.depuisLeCache)
      .map((p) => [p.id, p]),
  );
  return projets.map((p) => {
    const actuel = actuels.get(p.id);
    return actuel && actuel.updatedAt > p.updatedAt ? actuel : p;
  });
}

/** Le chargement proprement dit, un seul à la fois (cf. `load`). */
async function charger(): Promise<DashboardData> {
  const res = await authFetch(`${BASE}/dashboard`);
  const payload = await handleResponse<DashboardPayload>(res);

  const monuments = payload.monuments.map(toMonument);
  const projets = payload.projets.map(toProjet);
  const dossiers = payload.dossiers.map(toDossier);
  const suivis = Object.fromEntries(
    Object.entries(payload.suivis).map(([projetId, rows]) => [projetId, rows.map(toSuivi)]),
  );

  useMonumentStore.getState().setMonuments(monuments);
  useProjetStore.getState().setProjets(garderLesPlusRecents(projets));
  useDossierStore.getState().setDossiers(dossiers);
  useAideStore.getState().setDigests(payload.digests);
  const suiviStore = useSuiviStore.getState();
  for (const [projetId, list] of Object.entries(suivis)) {
    suiviStore.setForProjet(projetId, list);
  }

  return { monuments, projets, dossiers, digests: payload.digests, suivis };
}
