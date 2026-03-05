import { useMemo } from 'react';
import { useDossierStore } from '@/stores/useDossierStore';
import type { Dossier } from '@/types';

interface DossierProgress {
  total: number;
  fournis: number;
  enAttente: number;
  manquants: number;
  progressionPourcentage: number;
  isComplete: boolean;
}

export function useDossierProgress(dossierId: string): DossierProgress {
  const dossiers = useDossierStore((s) => s.dossiers);

  return useMemo(() => {
    const dossier = dossiers.find((d) => d.id === dossierId);
    if (!dossier) {
      return { total: 0, fournis: 0, enAttente: 0, manquants: 0, progressionPourcentage: 0, isComplete: false };
    }

    const obligatoires = dossier.checklist.filter((c) => c.obligatoire);
    const fournis = obligatoires.filter((c) => c.statut === 'fourni').length;
    const enAttente = obligatoires.filter((c) => c.statut === 'en_attente').length;
    const manquants = obligatoires.filter((c) => c.statut === 'manquant').length;

    return {
      total: obligatoires.length,
      fournis,
      enAttente,
      manquants,
      progressionPourcentage: obligatoires.length > 0 ? Math.round((fournis / obligatoires.length) * 100) : 0,
      isComplete: manquants === 0 && enAttente === 0,
    };
  }, [dossiers, dossierId]);
}

interface DossiersByStatus {
  brouillon: Dossier[];
  en_cours: Dossier[];
  complet: Dossier[];
  pret: Dossier[];
  soumis: Dossier[];
}

export function useDossiersByStatus(userId?: string): DossiersByStatus {
  const dossiers = useDossierStore((s) => s.dossiers);

  return useMemo(() => {
    const filtered = userId
      ? dossiers.filter((d) => d.userId === userId)
      : dossiers;

    return {
      brouillon: filtered.filter((d) => d.statut === 'brouillon'),
      en_cours: filtered.filter((d) => d.statut === 'en_cours'),
      complet: filtered.filter((d) => d.statut === 'complet'),
      pret: filtered.filter((d) => d.statut === 'pret'),
      soumis: filtered.filter((d) => d.statut === 'soumis'),
    };
  }, [dossiers, userId]);
}
