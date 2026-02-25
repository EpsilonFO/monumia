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
  brouillon: { label: 'Brouillon', color: 'bg-gray-100 text-gray-700' },
  en_cours: { label: 'En cours', color: 'bg-blue-100 text-blue-700' },
  complet: { label: 'Complet', color: 'bg-amber-100 text-amber-700' },
  pret: { label: 'Prêt à soumettre', color: 'bg-green-100 text-green-700' },
  soumis: { label: 'Soumis', color: 'bg-purple-100 text-purple-700' },
};

export const CHECKLIST_STATUS_CONFIG = {
  fourni: { label: 'Fourni', color: 'text-green-600', bgColor: 'bg-green-50' },
  en_attente: { label: 'En attente', color: 'text-amber-600', bgColor: 'bg-amber-50' },
  manquant: { label: 'Manquant', color: 'text-red-600', bgColor: 'bg-red-50' },
} as const;
