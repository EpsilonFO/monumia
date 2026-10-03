import { create } from 'zustand';

/**
 * Le retour de la page de détail ouverte (monument, projet, aide, dossier),
 * posé par `BoutonRetour` et lu par la barre haute.
 *
 * Sur téléphone, le carré bleu en tête de page coûtait une ligne entière avant
 * le contenu : la barre haute y affiche à la place la flèche et la page où elle
 * ramène. Une seule entrée, parce qu'une page n'a qu'un retour.
 */
export interface Retour {
  to: string;
  libelle: string;
}

interface RetourState {
  retour: Retour | null;
  poser: (retour: Retour) => void;
  /** Ne retire que le retour qu'on a posé : à la navigation d'un détail à un
   *  autre, celui de la page suivante est peut-être déjà en place. */
  retirer: (retour: Retour) => void;
}

export const useRetourStore = create<RetourState>()((set, get) => ({
  retour: null,
  poser: (retour) => set({ retour }),
  retirer: (retour) => {
    const actuel = get().retour;
    if (actuel && actuel.to === retour.to && actuel.libelle === retour.libelle) set({ retour: null });
  },
}));
