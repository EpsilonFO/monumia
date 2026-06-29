export const AIDE_CATEGORIES = [
  { value: 'etat_drac', label: 'État (DRAC)', color: 'bg-info-muted text-info' },
  { value: 'region', label: 'Région', color: 'bg-cat-violet-soft text-cat-violet' },
  { value: 'departement', label: 'Département', color: 'bg-cat-10-soft text-cat-10' },
  { value: 'fondation_patrimoine', label: 'Fondation du Patrimoine', color: 'bg-warning-muted text-warning' },
  { value: 'europe', label: 'Europe', color: 'bg-cat-1-soft text-cat-1' },
  { value: 'mecenat', label: 'Mécénat', color: 'bg-cat-2-soft text-cat-2' },
  { value: 'fiscalite', label: 'Fiscalité', color: 'bg-success-muted text-success' },
  { value: 'autre', label: 'Autre', color: 'bg-muted text-muted-foreground' },
] as const;

export const AIDE_TYPES = [
  { value: 'subvention', label: 'Subvention' },
  { value: 'avance', label: 'Avance remboursable' },
  { value: 'pret', label: 'Prêt' },
  { value: 'deduction_fiscale', label: 'Déduction fiscale' },
  { value: 'label', label: 'Label' },
  { value: 'mecenat', label: 'Mécénat' },
  { value: 'souscription', label: 'Souscription publique' },
  { value: 'autre', label: 'Autre' },
] as const;
