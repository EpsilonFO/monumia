import i18n from '@/i18n';
import type { ChecklistItemStatus } from '@/types';

export const DOSSIER_STEPS = [
  {
    step: 1 as const,
    get label() { return i18n.t('constants:dossierSteps.etapes.initialisation.label'); },
    get description() { return i18n.t('constants:dossierSteps.etapes.initialisation.description'); },
  },
  {
    step: 2 as const,
    get label() { return i18n.t('constants:dossierSteps.etapes.constitution.label'); },
    get description() { return i18n.t('constants:dossierSteps.etapes.constitution.description'); },
  },
  {
    step: 3 as const,
    get label() { return i18n.t('constants:dossierSteps.etapes.verification.label'); },
    get description() { return i18n.t('constants:dossierSteps.etapes.verification.description'); },
  },
  {
    step: 4 as const,
    get label() { return i18n.t('constants:dossierSteps.etapes.pret.label'); },
    get description() { return i18n.t('constants:dossierSteps.etapes.pret.description'); },
  },
  {
    step: 5 as const,
    get label() { return i18n.t('constants:dossierSteps.etapes.soumis.label'); },
    get description() { return i18n.t('constants:dossierSteps.etapes.soumis.description'); },
  },
] as const;

export const DOSSIER_STATUS_LABELS: Record<string, { label: string; color: string }> = {
  brouillon: { get label() { return i18n.t('constants:dossierSteps.statuts.brouillon'); }, color: 'bg-muted text-muted-foreground' },
  en_cours: { get label() { return i18n.t('constants:dossierSteps.statuts.en_cours'); }, color: 'bg-info-muted text-info' },
  complet: { get label() { return i18n.t('constants:dossierSteps.statuts.complet'); }, color: 'bg-warning-muted text-warning' },
  pret: { get label() { return i18n.t('constants:dossierSteps.statuts.pret'); }, color: 'bg-success-muted text-success' },
  soumis: { get label() { return i18n.t('constants:dossierSteps.statuts.soumis'); }, color: 'bg-cat-violet-soft text-cat-violet' },
};

// Typé sur ChecklistItemStatus (et non `as const` nu) : l'ajout d'un statut au
// type doit casser la compilation ici, pas produire un trou silencieux.
export const CHECKLIST_STATUS_CONFIG: Record<
  ChecklistItemStatus,
  { label: string; color: string; bgColor: string }
> = {
  fourni: { get label() { return i18n.t('constants:dossierSteps.checklist.fourni'); }, color: 'text-success', bgColor: 'bg-success-muted' },
  repris: { get label() { return i18n.t('constants:dossierSteps.checklist.repris'); }, color: 'text-primary', bgColor: 'bg-secondary' },
  en_attente: { get label() { return i18n.t('constants:dossierSteps.checklist.en_attente'); }, color: 'text-warning', bgColor: 'bg-warning-muted' },
  manquant: { get label() { return i18n.t('constants:dossierSteps.checklist.manquant'); }, color: 'text-destructive', bgColor: 'bg-destructive-muted' },
};
