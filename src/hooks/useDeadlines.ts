import { useMemo } from 'react';
import { useDossierStore } from '@/stores/useDossierStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { daysUntil, isUrgent } from '@/lib/date-utils';
import type { DossierEcheance } from '@/types';

interface DeadlineWithContext extends DossierEcheance {
  dossierId: string;
  dossierTitre: string;
  joursRestants: number;
  estUrgent: boolean;
}

export function useDeadlines(): DeadlineWithContext[] {
  const dossiers = useDossierStore((s) => s.dossiers);
  const user = useAuthStore((s) => s.user);

  return useMemo(() => {
    if (!user) return [];

    const userDossiers = dossiers.filter(
      (d) => d.userId === user.id && d.statut !== 'soumis'
    );

    const deadlines: DeadlineWithContext[] = [];

    for (const dossier of userDossiers) {
      for (const echeance of dossier.echeances) {
        if (echeance.accomplie) continue;

        const joursRestants = daysUntil(echeance.date);
        if (joursRestants < 0) continue; // skip past deadlines

        deadlines.push({
          ...echeance,
          dossierId: dossier.id,
          dossierTitre: dossier.titre,
          joursRestants,
          estUrgent: isUrgent(echeance.date),
        });
      }
    }

    return deadlines.sort((a, b) => a.joursRestants - b.joursRestants);
  }, [dossiers, user]);
}
