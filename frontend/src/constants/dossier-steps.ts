import type { ChecklistItemStatus } from '@/types';

export const DOSSIER_STEPS = [
  {
    step: 1 as const,
    label: 'Initialisation',
    description: 'Collecte des informations de base et identification des pièces nécessaires',
  },
  {
    step: 2 as const,
    label: 'Constitution',
    description: 'Rassemblement des documents et rédaction des sections du dossier',
  },
  {
    step: 3 as const,
    label: 'Vérification',
    description: 'Relecture du dossier complet et vérification de la conformité',
  },
  {
    step: 4 as const,
    label: 'Prêt à soumettre',
    description: 'Le dossier est complet et prêt pour le dépôt',
  },
  {
    step: 5 as const,
    label: 'Soumis',
    description: 'Le dossier a été déposé manuellement par le porteur de projet',
  },
] as const;

export const DOSSIER_STATUS_LABELS: Record<string, { label: string; color: string }> = {
  brouillon: { label: 'Brouillon', color: 'bg-muted text-muted-foreground' },
  en_cours: { label: 'En cours', color: 'bg-info-muted text-info' },
  complet: { label: 'Complet', color: 'bg-warning-muted text-warning' },
  pret: { label: 'Prêt à soumettre', color: 'bg-success-muted text-success' },
  soumis: { label: 'Soumis', color: 'bg-cat-violet-soft text-cat-violet' },
};

// Typé sur ChecklistItemStatus (et non `as const` nu) : l'ajout d'un statut au
// type doit casser la compilation ici, pas produire un trou silencieux.
export const CHECKLIST_STATUS_CONFIG: Record<
  ChecklistItemStatus,
  { label: string; color: string; bgColor: string }
> = {
  fourni: { label: 'Fourni', color: 'text-success', bgColor: 'bg-success-muted' },
  repris: { label: 'Repris — à vérifier', color: 'text-primary', bgColor: 'bg-secondary' },
  en_attente: { label: 'En attente', color: 'text-warning', bgColor: 'bg-warning-muted' },
  manquant: { label: 'Manquant', color: 'text-destructive', bgColor: 'bg-destructive-muted' },
};
