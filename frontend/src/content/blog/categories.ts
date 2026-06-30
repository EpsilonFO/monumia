export type BlogCategorySlug =
  | 'protections-statuts'
  | 'aides-financements'
  | 'demarches-dossiers'
  | 'travaux-techniques';

export interface BlogCategory {
  slug: BlogCategorySlug;
  label: string;
  description: string;
  /** Classes Tailwind d'accent pour les badges de catégorie. */
  accentClass: string;
}

export const BLOG_CATEGORIES: BlogCategory[] = [
  {
    slug: 'protections-statuts',
    label: 'Protections & statuts patrimoniaux',
    description:
      "Comprendre le statut de votre bien : Monument Historique classé ou inscrit, Site Patrimonial Remarquable, abords, base Mérimée.",
    accentClass: 'bg-blue-100 text-blue-800',
  },
  {
    slug: 'aides-financements',
    label: 'Aides & financements',
    description:
      'Subventions, taux et plafonds, cofinancement, fiscalité : pour vous y retrouver dans les financements du patrimoine.',
    accentClass: 'bg-amber-100 text-amber-800',
  },
  {
    slug: 'demarches-dossiers',
    label: 'Démarches & dossiers',
    description:
      'Diagnostic, étude préalable, pièces du dossier, échéances : réussir vos démarches administratives.',
    accentClass: 'bg-emerald-100 text-emerald-800',
  },
  {
    slug: 'travaux-techniques',
    label: 'Travaux & techniques de restauration',
    description:
      "Le vocabulaire technique des travaux : maîtrise d'ouvrage et d'œuvre, lots, matériaux et corps de métier.",
    accentClass: 'bg-rose-100 text-rose-800',
  },
];

export function getCategory(slug: string): BlogCategory | undefined {
  return BLOG_CATEGORIES.find((c) => c.slug === slug);
}
