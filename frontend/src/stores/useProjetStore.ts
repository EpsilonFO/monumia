import { create } from 'zustand';
import { projetService } from '@/services/projet.service';
import type { Projet } from '@/types';

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

export const useProjetStore = create<ProjetState>()((set, get) => ({
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
      // URL) : on relit le projet plutôt que d'écrire par-dessus un vide.
      const connu = get().getProjet(projetId);
      const projet = connu ?? (await projetService.getById(projetId));
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
}));
