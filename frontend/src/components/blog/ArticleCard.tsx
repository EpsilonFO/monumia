import { Link } from 'react-router';

import type { BlogArticle } from '@/content/blog/articles';
import { getCategory } from '@/content/blog/categories';
import { C } from '@/lib/brand';
import { IconTemps } from '@/components/icons';
import { CategoryBadge } from './CategoryBadge';

export function ArticleCard({ article }: { article: BlogArticle }) {
  const category = getCategory(article.categorySlug);
  return (
    <Link
      to={`/blog/article/${article.slug}`}
      className="group flex flex-col rounded-2xl border p-5 transition-all duration-300 hover:-translate-y-0.5"
      style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' }}
    >
      <div>
        {category && <CategoryBadge category={category} />}
      </div>
      <h3
        className="mt-3 text-[19px] font-normal leading-snug"
        style={{ fontFamily: 'var(--font-serif)', color: C.ink }}
      >
        {article.title}
      </h3>
      <p className="mt-2 line-clamp-3 text-[13px] leading-relaxed" style={{ color: C.grayFg }}>
        {article.excerpt}
      </p>
      <div className="mt-4 flex items-center gap-3">
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
    </Link>
  );
}
