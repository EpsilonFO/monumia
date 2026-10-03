import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { projetService } from '@/services/projet.service';
import type { Projet } from '@/types';
import { enregistrerCache, optionsDeCache } from './persistance';

/**
 * Ce que le cache garde d'un projet : tout, SAUF le rôle de l'utilisateur.
 * Même règle que `monumentPourLeCache` : `myRole` gouverne l'onglet Aides,
 * l'édition et la suppression du chantier, et ce qui ouvre un droit attend la
 * réponse du serveur. Un projet relu du cache a donc un rôle INCONNU, pas nul :
 * les pages lisent `depuisLeCache` avant d'en tirer un repli.
 */
export function projetPourLeCache(projet: Projet): Projet {
  const reste = { ...projet };
  delete reste.myRole;
  return reste;
}

interface ProjetCache {
  projets: Projet[];
}

/**
 * Une chaîne de promesses PAR PROJET : les réponses envoyées depuis deux cartes
 * d'aide à la suite s'écraseraient sinon. `update_projet` remplace
 * `questionnaire` EN BLOC (cf. routers/projets.py) — deux requêtes parties
 * ensemble liraient le même état de départ, et la seconde à répondre perdrait
 * la réponse de la première. Sérialiser est le seul remède tant que l'écriture
 * n'est pas une fusion côté serveur.
 */
const chaines = new Map<string, Promise<unknown>>();

interface ProjetState {
  projets: Projet[];
  loaded: boolean;

  setProjets: (projets: Projet[]) => void;
  getProjet: (id: string) => Projet | undefined;
  getProjetsByMonument: (monumentId: string) => Projet[];
  addProjet: (projet: Projet) => void;
  /** Remplace le projet s'il est déjà là (rafraîchissement serveur), sinon l'ajoute. */
  upsertProjet: (projet: Projet) => void;
  deleteProjet: (id: string) => void;
  /**
   * Enregistre UNE réponse du questionnaire sur le projet, depuis n'importe où
   * (carte d'aide, fiche d'aide). `value === undefined` efface la réponse.
   * Rejette en cas d'échec : c'est l'appelant qui sait quoi dire à l'écran.
   */
  repondreFait: (
    projetId: string,
    factKey: string,
    value: string | string[] | undefined,
  ) => Promise<void>;
}

export const useProjetStore = create<ProjetState>()(persist((set, get) => ({
  projets: [],
  loaded: false,

  setProjets: (projets) => set({ projets, loaded: true }),

  getProjet: (id) => get().projets.find((p) => p.id === id),

  getProjetsByMonument: (monumentId) =>
    get().projets.filter((p) => p.monumentId === monumentId),

  addProjet: (projet) => set((state) => ({ projets: [projet, ...state.projets] })),

  upsertProjet: (projet) =>
    set((state) =>
      state.projets.some((p) => p.id === projet.id)
        ? { projets: state.projets.map((p) => (p.id === projet.id ? projet : p)) }
        : { projets: [projet, ...state.projets] }
    ),

  deleteProjet: (id) =>
    set((state) => ({ projets: state.projets.filter((p) => p.id !== id) })),

  repondreFait: (projetId, factKey, value) => {
    const ecrire = async () => {
      // Lecture du questionnaire AU MOMENT DE PARTIR, pas à la création du
      // callback : la réponse précédente de la file est déjà enregistrée, et
      // c'est sur elle qu'il faut bâtir. Store non hydraté (arrivée directe par
      // URL) : on relit le projet plutôt que d'écrire par-dessus un vide. Même
      // chose pour un projet relu du cache local : son questionnaire peut avoir
      // bougé depuis (autre onglet, autre membre), et le remplacer en bloc
      // effacerait ces réponses-là.
      const connu = get().getProjet(projetId);
      const projet =
        connu && !connu.depuisLeCache ? connu : await projetService.getById(projetId);
      const questionnaire = { ...(projet.questionnaire ?? {}) };
      if (value === undefined) delete questionnaire[factKey];
      else questionnaire[factKey] = value;
      get().upsertProjet(await projetService.update(projetId, { questionnaire }));
    };
    const precedent = chaines.get(projetId) ?? Promise.resolve();
    const travail = precedent.then(ecrire, ecrire);
    // La file continue même après un échec — une réponse ratée ne doit pas
    // bloquer la suivante —, mais l'appelant, lui, voit bien son erreur.
    chaines.set(
      projetId,
      travail.catch(() => {}),
    );
    return travail;
  },
}), optionsDeCache<ProjetState, ProjetCache>({
  domaine: 'projets',
  // v2 : le rôle ne s'écrit plus. Les entrées v1, qui le portaient, sont jetées.
  version: 2,
  // `loaded` reste hors du cache : il dit « le serveur a répondu », et les
  // gardes anti-doublon s'y fient.
  partialize: (state) => ({ projets: state.projets.map(projetPourLeCache) }),
  relire: (persiste, courant) => ({
    ...courant,
    projets: (persiste.projets ?? []).map((p) => ({
      ...projetPourLeCache(p),
      depuisLeCache: true,
    })),
  }),
})));

enregistrerCache(useProjetStore, () => useProjetStore.setState({ projets: [], loaded: false }));
