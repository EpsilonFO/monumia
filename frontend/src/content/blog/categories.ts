import {
  IconProtection,
  IconSubvention,
  IconDossier,
  IconChantier,
  type IconComponent,
} from '@/components/icons';
import i18n from '@/i18n';

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

/** Clé de la catégorie dans le namespace `blog`. */
type CleCategorie =
  | 'protectionsStatuts'
  | 'aidesFinancements'
  | 'demarchesDossiers'
  | 'travauxTechniques';

// Libellés en getters : traduits à la lecture, jamais à l'import.
function categorie(
  slug: BlogCategorySlug,
  cle: CleCategorie,
  tone: BlogCategory['tone'],
  icon: IconComponent,
): BlogCategory {
  return {
    slug,
    tone,
    icon,
    get label() {
      return i18n.t(`blog:categories.${cle}.libelle`);
    },
    get shortLabel() {
      return i18n.t(`blog:categories.${cle}.libelleCourt`);
    },
    get description() {
      return i18n.t(`blog:categories.${cle}.description`);
    },
    get stepLabel() {
      return i18n.t(`blog:categories.${cle}.etape`);
    },
  };
}

export const BLOG_CATEGORIES: BlogCategory[] = [
  categorie('protections-statuts', 'protectionsStatuts', 1, IconProtection),
  categorie('aides-financements', 'aidesFinancements', 2, IconSubvention),
  categorie('demarches-dossiers', 'demarchesDossiers', 3, IconDossier),
  categorie('travaux-techniques', 'travauxTechniques', 4, IconChantier),
];

export function getCategory(slug: string): BlogCategory | undefined {
  return BLOG_CATEGORIES.find((c) => c.slug === slug);
}

/** Couleurs de la catégorie sous forme de tokens CSS (fg = plein, soft = fond). */
export function categoryTone(category: BlogCategory): { fg: string; soft: string } {
  return { fg: `var(--cat-${category.tone})`, soft: `var(--cat-${category.tone}-soft)` };
}
