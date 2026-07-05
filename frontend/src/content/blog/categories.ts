import {
  IconProtection,
  IconSubvention,
  IconDossier,
  IconChantier,
  type IconComponent,
} from '@/components/icons';

export type BlogCategorySlug =
  | 'protections-statuts'
  | 'aides-financements'
  | 'demarches-dossiers'
  | 'travaux-techniques';

export interface BlogCategory {
  slug: BlogCategorySlug;
  label: string;
  /** Libellé court pour les badges (le `label` complet reste pour les titres). */
  shortLabel: string;
  description: string;
  /** Numéro de token de couleur `--cat-N` / `--cat-N-soft`. */
  tone: 1 | 2 | 3 | 4;
  /** Icône de la catégorie (banque @/components/icons). */
  icon: IconComponent;
  /** Verbe d'action court du parcours (carte-parcours). */
  stepLabel: string;
}

export const BLOG_CATEGORIES: BlogCategory[] = [
  {
    slug: 'protections-statuts',
    label: 'Protections & statuts patrimoniaux',
    shortLabel: 'Protections & statuts',
    description:
      "Comprendre le statut de votre bien : Monument Historique classé ou inscrit, Site Patrimonial Remarquable, abords, base Mérimée.",
    tone: 1,
    icon: IconProtection,
    stepLabel: 'Comprendre mon statut',
  },
  {
    slug: 'aides-financements',
    label: 'Aides & financements',
    shortLabel: 'Aides & financements',
    description:
      'Subventions, taux et plafonds, cofinancement, fiscalité : pour vous y retrouver dans les financements du patrimoine.',
    tone: 2,
    icon: IconSubvention,
    stepLabel: 'Trouver mes aides',
  },
  {
    slug: 'demarches-dossiers',
    label: 'Démarches & dossiers',
    shortLabel: 'Démarches & dossiers',
    description:
      'Diagnostic, étude préalable, pièces du dossier, échéances : réussir vos démarches administratives.',
    tone: 3,
    icon: IconDossier,
    stepLabel: 'Monter mon dossier',
  },
  {
    slug: 'travaux-techniques',
    label: 'Travaux & techniques de restauration',
    shortLabel: 'Travaux & techniques',
    description:
      "Le vocabulaire technique des travaux : maîtrise d'ouvrage et d'œuvre, lots, matériaux et corps de métier.",
    tone: 4,
    icon: IconChantier,
    stepLabel: 'Lancer les travaux',
  },
];

export function getCategory(slug: string): BlogCategory | undefined {
  return BLOG_CATEGORIES.find((c) => c.slug === slug);
}

/** Couleurs de la catégorie sous forme de tokens CSS (fg = plein, soft = fond). */
export function categoryTone(category: BlogCategory): { fg: string; soft: string } {
  return { fg: `var(--cat-${category.tone})`, soft: `var(--cat-${category.tone}-soft)` };
}
