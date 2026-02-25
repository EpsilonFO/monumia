import { useMemo, useCallback } from 'react';
import { useAideStore } from '@/stores/useAideStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { aideService } from '@/services/aide.service';
import type { AideDiagnosticResult, WorkType } from '@/types';

export function useAideDiagnostic(monumentId?: string) {
  const user = useAuthStore((s) => s.user);
  const monuments = useMonumentStore((s) => s.monuments);
  const filters = useAideStore((s) => s.filters);
  const lastDiagnostic = useAideStore((s) => s.lastDiagnostic);

  const monument = useMemo(
    () => (monumentId ? monuments.find((m) => m.id === monumentId) : undefined),
    [monumentId, monuments]
  );

  const runDiagnostic = useCallback(
    (modeProjet?: boolean, travauxFiltres?: WorkType[]): AideDiagnosticResult | null => {
      if (!monument || !user) return null;
      return aideService.runDiagnostic(
        monument,
        user,
        modeProjet ?? filters.modeProjet,
        travauxFiltres ?? (filters.travauxFiltres.length > 0 ? filters.travauxFiltres : undefined)
      );
    },
    [monument, user, filters.modeProjet, filters.travauxFiltres]
  );

  return {
    monument,
    user,
    lastDiagnostic,
    filters,
    runDiagnostic,
    isReady: !!monument && !!user,
  };
}
