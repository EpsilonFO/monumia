import type { Aide, AideCategory, AideDiagnosticResult, Monument, User, WorkType } from '@/types';
import { useAideStore } from '@/stores/useAideStore';
import { runDiagnostic } from '@/lib/matching-engine';

export const aideService = {
  getAll(): Aide[] {
    return useAideStore.getState().aides;
  },

  getById(id: string): Aide | undefined {
    return useAideStore.getState().getAide(id);
  },

  getByCategory(category: AideCategory): Aide[] {
    return useAideStore.getState().aides.filter((a) => a.categorie === category);
  },

  search(query: string): Aide[] {
    const q = query.toLowerCase();
    return useAideStore.getState().aides.filter(
      (a) =>
        a.nom.toLowerCase().includes(q) ||
        a.nomCourt.toLowerCase().includes(q) ||
        a.description.toLowerCase().includes(q) ||
        a.organisme.toLowerCase().includes(q)
    );
  },

  runDiagnostic(
    monument: Monument,
    user: User,
    modeProjet: boolean = false,
    travauxFiltres?: WorkType[]
  ): AideDiagnosticResult {
    const aides = useAideStore.getState().aides;
    const result = runDiagnostic(monument, user, aides, modeProjet, travauxFiltres);
    useAideStore.getState().setLastDiagnostic(result);
    return result;
  },

  getFilteredAides(
    categories: AideCategory[],
    searchQuery: string
  ): Aide[] {
    let filtered = useAideStore.getState().aides;

    if (categories.length > 0) {
      filtered = filtered.filter((a) => categories.includes(a.categorie));
    }

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (a) =>
          a.nom.toLowerCase().includes(q) ||
          a.nomCourt.toLowerCase().includes(q) ||
          a.organisme.toLowerCase().includes(q)
      );
    }

    return filtered;
  },
};
