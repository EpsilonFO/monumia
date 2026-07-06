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

// Vite renvoie le contenu brut de chaque .md (?raw), en import paresseux.
const bodies = import.meta.glob('./articles/*.md', {
  query: '?raw',
  import: 'default',
}) as Record<string, () => Promise<string>>;

function bodyLoader(slug: string): () => Promise<string> {
  const loader = bodies[`./articles/${slug}.md`];
  if (!loader) {
    return async () =>
      `# Article introuvable\n\nLe contenu « ${slug} » n'a pas encore été rédigé.`;
  }
  return loader;
}

type ArticleMeta = Omit<BlogArticle, 'body'>;

const ARTICLE_META: ArticleMeta[] = [
  // Protections & statuts
  {
    slug: 'classe-ou-inscrit',
    icon: IconRegle,
    title: 'Classé ou inscrit : quelle différence ?',
    categorySlug: 'protections-statuts',
    excerpt:
      "Classement et inscription sont deux niveaux de protection au titre des Monuments Historiques. On vous explique ce qui change concrètement.",
    relatedTermKeys: ['monument-classe', 'monument-inscrit'],
    readingTimeMin: 6,
    publishedAt: '2026-06-16',
  },
  {
    slug: 'site-patrimonial-remarquable',
    icon: IconLocalisation,
    title: 'Le Site Patrimonial Remarquable (SPR)',
    categorySlug: 'protections-statuts',
    excerpt:
      "Le SPR protège des ensembles urbains ou paysagers. Ce que cela implique pour un bien situé dans son périmètre.",
    relatedTermKeys: ['spr'],
    readingTimeMin: 6,
    publishedAt: '2026-06-17',
  },
  {
    slug: 'perimetre-et-abords',
    icon: IconCadastre,
    title: "Périmètre et abords d'un Monument Historique",
    categorySlug: 'protections-statuts',
    excerpt:
      "Être « aux abords » d'un Monument Historique change vos obligations, même si votre bien n'est pas protégé lui-même.",
    relatedTermKeys: ['perimetre-abords'],
    readingTimeMin: 6,
    publishedAt: '2026-06-17',
  },
  {
    slug: 'base-merimee',
    icon: IconLivre,
    title: "La base Mérimée, mode d'emploi",
    categorySlug: 'protections-statuts',
    excerpt:
      "La base Mérimée recense le patrimoine architectural français. Comment y retrouver votre bien et sa référence.",
    relatedTermKeys: ['merimee'],
  },
  // Aides & financements
  {
    slug: 'taux-plafond-base-eligible',
    icon: IconTendance,
    title: 'Taux, plafond et base éligible : comment lire une aide',
    categorySlug: 'aides-financements',
    excerpt:
      'Trois notions qui déterminent ce que vous toucherez réellement. On les décode avec un exemple chiffré.',
    relatedTermKeys: ['taux-maximum', 'montant-maximum', 'base-eligible'],
  },
  {
    slug: 'subvention-vs-pret',
    icon: IconAide,
    title: 'Subvention, avance remboursable, prêt : les différences',
    categorySlug: 'aides-financements',
    excerpt:
      'Toutes les aides ne se valent pas. Distinguez ce que vous gardez de ce que vous devrez rendre.',
    relatedTermKeys: ['subvention'],
    readingTimeMin: 7,
    publishedAt: '2026-06-18',
  },
  {
    slug: 'cofinancement',
    icon: IconEquipe,
    title: 'Le cofinancement expliqué simplement',
    categorySlug: 'aides-financements',
    excerpt:
      "Beaucoup d'aides exigent que d'autres financeurs participent. Comment monter un plan de financement cohérent.",
    relatedTermKeys: ['cofinancement'],
  },
  {
    slug: 'drac',
    icon: IconInstitution,
    title: 'La DRAC : rôle et interlocuteurs',
    categorySlug: 'aides-financements',
    excerpt:
      "La Direction régionale des affaires culturelles est votre interlocuteur clé pour le patrimoine protégé.",
    relatedTermKeys: ['drac'],
    readingTimeMin: 7,
    publishedAt: '2026-06-18',
  },
  // Démarches & dossiers
  {
    slug: 'etat-de-conservation',
    icon: IconVoir,
    title: 'État de conservation et urgence des travaux',
    categorySlug: 'demarches-dossiers',
    excerpt:
      "Comment évaluer honnêtement l’état de votre bien : ces notions conditionnent votre éligibilité aux aides.",
    relatedTermKeys: ['etat-conservation', 'urgence-travaux'],
  },
  {
    slug: 'etude-prealable',
    icon: IconEtapes,
    title: "L'étude préalable, étape par étape",
    categorySlug: 'demarches-dossiers',
    excerpt:
      "Souvent obligatoire avant des travaux sur un Monument Historique. À quoi elle sert et qui la réalise.",
    relatedTermKeys: ['etude-prealable'],
    readingTimeMin: 7,
    publishedAt: '2026-06-18',
  },
  {
    slug: 'diagnostic-prealable',
    icon: IconDiagnostic,
    title: 'Le diagnostic préalable : pourquoi, comment',
    categorySlug: 'demarches-dossiers',
    excerpt:
      'Le diagnostic dresse un état des lieux qui oriente votre projet et débloque certaines aides.',
    relatedTermKeys: ['diagnostic'],
  },
  // Travaux & techniques
  {
    slug: 'maitrise-ouvrage-oeuvre',
    icon: IconPlan,
    title: "Maîtrise d'ouvrage et maîtrise d'œuvre",
    categorySlug: 'travaux-techniques',
    excerpt:
      "Qui décide, qui conçoit, qui exécute ? Deux rôles à ne pas confondre dans un projet de restauration.",
    relatedTermKeys: ['maitrise-ouvrage', 'maitrise-oeuvre'],
  },
];

export const BLOG_ARTICLES: BlogArticle[] = ARTICLE_META.map((m) => ({
  ...m,
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
