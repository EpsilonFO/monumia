import { Link } from 'react-router';

import type { BlogArticle } from '@/content/blog/articles';
import { categoryTone, getCategory } from '@/content/blog/categories';
import { C } from '@/lib/brand';
import { IconTemps } from '@/components/icons';
import { BandMotif } from './BandMotif';
import { CategoryBadge } from './CategoryBadge';

/** Date de publication au format éditorial français (« 18 juin 2026 »). */
function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

export function ArticleCard({ article }: { article: BlogArticle }) {
  const category = getCategory(article.categorySlug);
  const tone = category ? categoryTone(category) : null;
  const Icon = article.icon ?? category?.icon;
  return (
    <Link
      to={`/blog/article/${article.slug}`}
      className="group flex flex-col overflow-hidden rounded-2xl border transition-all duration-300 hover:-translate-y-0.5"
      style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' }}
    >
      {/* Bandeau de couverture : teinte + icône du thème (le blog n’utilise pas de photos) */}
      {tone && Icon && (
        <div
          aria-hidden
          className="relative flex h-28 shrink-0 items-center justify-center overflow-hidden"
          style={{ background: tone.soft, color: tone.fg }}
        >
          {/* Voile qui distingue le bandeau quand la carte repose sur un panneau de même teinte */}
          <span className="absolute inset-0" style={{ background: tone.fg, opacity: 0.04 }} />
          <BandMotif
            slug={article.slug}
            className="absolute -right-3 bottom-0 h-16 w-auto opacity-[0.13]"
          />
          <Icon className="relative h-12 w-12 transition-transform duration-300 group-hover:-rotate-6 group-hover:scale-110" />
        </div>
      )}
      <div className="flex flex-1 flex-col p-5">
        <div className="flex flex-wrap items-center gap-2.5">
          {category && <CategoryBadge category={category} />}
          {article.publishedAt && (
            <span className="text-[11px] font-medium" style={{ color: C.grayMuted }}>
              {formatDate(article.publishedAt)}
            </span>
          )}
        </div>
        <h3
          className="mt-3 text-[19px] font-normal leading-snug"
          style={{ fontFamily: 'var(--font-serif)', color: C.ink }}
        >
          {article.title}
        </h3>
        <p className="mt-2 line-clamp-2 text-[13px] leading-relaxed" style={{ color: C.grayFg }}>
          {article.excerpt}
        </p>
        <div className="mt-auto flex items-center gap-3 pt-4">
          <span
            className="text-[13px] font-semibold group-hover:underline"
            style={{ color: C.orange }}
          >
            Lire l’article →
          </span>
          {article.readingTimeMin && (
            <span
              className="inline-flex shrink-0 items-center gap-1 whitespace-nowrap text-[11px] font-medium"
              style={{ color: C.grayMuted }}
            >
              <IconTemps className="h-3.5 w-3.5" /> {article.readingTimeMin} min
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
