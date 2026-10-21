import type { ComponentType } from 'react';

import {
  IconAide,
  IconCadastre,
  IconDiagnostic,
  IconEquipe,
  IconEtapes,
  IconInstitution,
  IconLivre,
  IconLocalisation,
  IconPlan,
  IconRegle,
  IconTendance,
  IconVoir,
} from '@/components/icons';
import i18n, { LANGUE_PAR_DEFAUT, langueCourante } from '@/i18n';
import type { BlogCategorySlug } from './categories';

export interface BlogArticle {
  slug: string;
  title: string;
  categorySlug: BlogCategorySlug;
  excerpt: string;
  /** Clés du glossaire abordées par l'article (réciproque du lien terme → article). */
  relatedTermKeys: string[];
  readingTimeMin?: number;
  /** Date de publication ISO (AAAA-MM-JJ), optionnelle pour les stubs. */
  publishedAt?: string;
  /** Icône propre à l'article (bandeau de carte) — à défaut, celle de la catégorie. */
  icon?: ComponentType<{ className?: string }>;
  /** Charge le corps Markdown en lazy. */
  body: () => Promise<string>;
}

// Vite renvoie le contenu brut de chaque .md (?raw), en import paresseux. Le français
// est à la racine de `articles/`, chaque autre langue dans son sous-dossier
// (`articles/en/<slug>.md`).
const bodies = import.meta.glob('./articles/**/*.md', {
  query: '?raw',
  import: 'default',
}) as Record<string, () => Promise<string>>;

function bodyLoader(slug: string): () => Promise<string> {
  // La langue se lit à l'appel : un article pas encore traduit retombe sur le français.
  return () => {
    const langue = langueCourante();
    const loader =
      (langue !== LANGUE_PAR_DEFAUT ? bodies[`./articles/${langue}/${slug}.md`] : undefined) ??
      bodies[`./articles/${slug}.md`];
    if (!loader) return Promise.resolve(i18n.t('blog:articles.contenuIntrouvable', { slug }));
    return loader();
  };
}

/** Clé de l'article dans le namespace `blog` (titre et extrait). */
type CleArticle =
  | 'classeOuInscrit'
  | 'sitePatrimonialRemarquable'
  | 'perimetreEtAbords'
  | 'baseMerimee'
  | 'tauxPlafondBaseEligible'
  | 'subventionVsPret'
  | 'cofinancement'
  | 'drac'
  | 'etatDeConservation'
  | 'etudePrealable'
  | 'diagnosticPrealable'
  | 'maitriseOuvrageOeuvre';

type ArticleMeta = Omit<BlogArticle, 'body' | 'title' | 'excerpt'> & { cle: CleArticle };

const ARTICLE_META: ArticleMeta[] = [
  // Protections & statuts
  {
    slug: 'classe-ou-inscrit',
    cle: 'classeOuInscrit',
    icon: IconRegle,
    categorySlug: 'protections-statuts',
    relatedTermKeys: ['monument-classe', 'monument-inscrit'],
    readingTimeMin: 6,
    publishedAt: '2026-06-16',
  },
  {
    slug: 'site-patrimonial-remarquable',
    cle: 'sitePatrimonialRemarquable',
    icon: IconLocalisation,
    categorySlug: 'protections-statuts',
    relatedTermKeys: ['spr'],
    readingTimeMin: 6,
    publishedAt: '2026-06-17',
  },
  {
    slug: 'perimetre-et-abords',
    cle: 'perimetreEtAbords',
    icon: IconCadastre,
    categorySlug: 'protections-statuts',
    relatedTermKeys: ['perimetre-abords'],
    readingTimeMin: 6,
    publishedAt: '2026-06-17',
  },
  {
    slug: 'base-merimee',
    cle: 'baseMerimee',
    icon: IconLivre,
    categorySlug: 'protections-statuts',
    relatedTermKeys: ['merimee'],
  },
  // Aides & financements
  {
    slug: 'taux-plafond-base-eligible',
    cle: 'tauxPlafondBaseEligible',
    icon: IconTendance,
    categorySlug: 'aides-financements',
    relatedTermKeys: ['taux-maximum', 'montant-maximum', 'base-eligible'],
  },
  {
    slug: 'subvention-vs-pret',
    cle: 'subventionVsPret',
    icon: IconAide,
    categorySlug: 'aides-financements',
    relatedTermKeys: ['subvention'],
    readingTimeMin: 7,
    publishedAt: '2026-06-18',
  },
  {
    slug: 'cofinancement',
    cle: 'cofinancement',
    icon: IconEquipe,
    categorySlug: 'aides-financements',
    relatedTermKeys: ['cofinancement'],
  },
  {
    slug: 'drac',
    cle: 'drac',
    icon: IconInstitution,
    categorySlug: 'aides-financements',
    relatedTermKeys: ['drac'],
    readingTimeMin: 7,
    publishedAt: '2026-06-18',
  },
  // Démarches & dossiers
  {
    slug: 'etat-de-conservation',
    cle: 'etatDeConservation',
    icon: IconVoir,
    categorySlug: 'demarches-dossiers',
    relatedTermKeys: ['etat-conservation', 'urgence-travaux'],
  },
  {
    slug: 'etude-prealable',
    cle: 'etudePrealable',
    icon: IconEtapes,
    categorySlug: 'demarches-dossiers',
    relatedTermKeys: ['etude-prealable'],
    readingTimeMin: 7,
    publishedAt: '2026-06-18',
  },
  {
    slug: 'diagnostic-prealable',
    cle: 'diagnosticPrealable',
    icon: IconDiagnostic,
    categorySlug: 'demarches-dossiers',
    relatedTermKeys: ['diagnostic'],
  },
  // Travaux & techniques
  {
    slug: 'maitrise-ouvrage-oeuvre',
    cle: 'maitriseOuvrageOeuvre',
    icon: IconPlan,
    categorySlug: 'travaux-techniques',
    relatedTermKeys: ['maitrise-ouvrage', 'maitrise-oeuvre'],
  },
];

// Titre et extrait en getters : traduits à la lecture, jamais à l'import.
export const BLOG_ARTICLES: BlogArticle[] = ARTICLE_META.map(({ cle, ...m }) => ({
  ...m,
  get title() {
    return i18n.t(`blog:articles.${cle}.titre`);
  },
  get excerpt() {
    return i18n.t(`blog:articles.${cle}.extrait`);
  },
  body: bodyLoader(m.slug),
}));

export function getAllArticles(): BlogArticle[] {
  return BLOG_ARTICLES;
}

export function getArticleBySlug(slug: string): BlogArticle | undefined {
  return BLOG_ARTICLES.find((a) => a.slug === slug);
}

export function getArticlesByCategory(categorySlug: string): BlogArticle[] {
  return BLOG_ARTICLES.filter((a) => a.categorySlug === categorySlug);
}
