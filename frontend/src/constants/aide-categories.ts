export const AIDE_CATEGORIES = [
  { value: 'etat_drac', label: 'État (DRAC)', color: 'bg-blue-100 text-blue-800' },
  { value: 'region', label: 'Région', color: 'bg-purple-100 text-purple-800' },
  { value: 'departement', label: 'Département', color: 'bg-indigo-100 text-indigo-800' },
  { value: 'fondation_patrimoine', label: 'Fondation du Patrimoine', color: 'bg-amber-100 text-amber-800' },
  { value: 'europe', label: 'Europe', color: 'bg-cyan-100 text-cyan-800' },
  { value: 'mecenat', label: 'Mécénat', color: 'bg-emerald-100 text-emerald-800' },
  { value: 'fiscalite', label: 'Fiscalité', color: 'bg-rose-100 text-rose-800' },
  { value: 'autre', label: 'Autre', color: 'bg-gray-100 text-gray-800' },
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
