import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Monument, MonumentPhoto } from '@/types';
import { enregistrerCache, optionsDeCache } from './persistance';

/**
 * Ce que le cache garde d'un monument : tout, SAUF ce qui ouvre un droit.
 *
 * `offre` gouverne l'onglet Équipe, l'échéancier, les aides « bientôt » et la
 * suppression (cf. `useOffreMonument`) : la persister reviendrait exactement à
 * ce que `useBillingStore` interdit, n'importe qui éditerait la clé pour
 * s'ouvrir Multi-monuments côté interface. `myRole` et `members` suivent la
 * même règle — ce sont les droits d'équipe sur le bien. Les zones qu'ils
 * gouvernent attendent donc le serveur, et seul le contenu s'affiche depuis le
 * cache.
 */
export function monumentPourLeCache(monument: Monument): Monument {
  const reste = { ...monument };
  delete reste.offre;
  delete reste.myRole;
  delete reste.members;
  return reste;
}

interface MonumentCache {
  monuments: Monument[];
}

interface MonumentState {
  monuments: Monument[];
  activeMonumentId: string | null;

  setMonuments: (monuments: Monument[]) => void;
  setActiveMonument: (id: string | null) => void;
  getMonument: (id: string) => Monument | undefined;
  addMonument: (monument: Monument) => void;
  upsertMonument: (monument: Monument) => void;
  updateMonument: (id: string, updates: Partial<Monument>) => void;
  deleteMonument: (id: string) => void;
  addPhoto: (monumentId: string, photo: MonumentPhoto) => void;
  removePhoto: (monumentId: string, photoId: string) => void;
}

export const useMonumentStore = create<MonumentState>()(persist((set, get) => ({
  monuments: [],
  activeMonumentId: null,

  setMonuments: (monuments) => set({ monuments }),

  setActiveMonument: (id) => set({ activeMonumentId: id }),

  getMonument: (id) => get().monuments.find((m) => m.id === id),

  addMonument: (monument) =>
    set((state) => ({ monuments: [monument, ...state.monuments] })),

  // Remplace le monument s'il est déjà présent (rafraîchissement serveur),
  // sinon l'ajoute. Préserve les valeurs serveur (pas d'écrasement d'updatedAt).
  upsertMonument: (monument) =>
    set((state) =>
      state.monuments.some((m) => m.id === monument.id)
        ? { monuments: state.monuments.map((m) => (m.id === monument.id ? monument : m)) }
        : { monuments: [monument, ...state.monuments] }
    ),

  updateMonument: (id, updates) =>
    set((state) => ({
      monuments: state.monuments.map((m) =>
        m.id === id
          ? { ...m, ...updates, updatedAt: new Date().toISOString() }
          : m
      ),
    })),

  deleteMonument: (id) =>
    set((state) => ({
      monuments: state.monuments.filter((m) => m.id !== id),
      activeMonumentId:
        state.activeMonumentId === id ? null : state.activeMonumentId,
    })),

  addPhoto: (monumentId, photo) =>
    set((state) => ({
      monuments: state.monuments.map((m) =>
        m.id === monumentId
          ? { ...m, photos: [...m.photos, photo], updatedAt: new Date().toISOString() }
          : m
      ),
    })),

  removePhoto: (monumentId, photoId) =>
    set((state) => ({
      monuments: state.monuments.map((m) =>
        m.id === monumentId
          ? {
              ...m,
              photos: m.photos.filter((p) => p.id !== photoId),
              updatedAt: new Date().toISOString(),
            }
          : m
      ),
    })),
}), optionsDeCache<MonumentState, MonumentCache>({
  domaine: 'monuments',
  version: 1,
  partialize: (state) => ({ monuments: state.monuments.map(monumentPourLeCache) }),
  relire: (persiste, courant) => ({
    ...courant,
    monuments: (persiste.monuments ?? []).map((m) => ({
      ...monumentPourLeCache(m),
      depuisLeCache: true,
    })),
  }),
})));

enregistrerCache(useMonumentStore, () =>
  useMonumentStore.setState({ monuments: [], activeMonumentId: null }),
);
