import { Link } from 'react-router';

import type { BlogArticle } from '@/content/blog/articles';
import { getCategory } from '@/content/blog/categories';
import { C } from '@/lib/brand';
import { IconSucces, IconTemps } from '@/components/icons';
import { useReadArticles } from './useReadArticles';
import { CategoryBadge } from './CategoryBadge';

export function ArticleCard({ article }: { article: BlogArticle }) {
  const category = getCategory(article.categorySlug);
  const { isRead } = useReadArticles();
  const read = isRead(article.slug);

  return (
    <Link
      to={`/blog/article/${article.slug}`}
      className="group flex flex-col rounded-2xl border p-5 transition-all duration-300 hover:-translate-y-0.5"
      style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' }}
    >
      <div className="flex items-center justify-between gap-2">
        {category && <CategoryBadge category={category} />}
        {read ? (
          <span
            className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold"
            style={{ background: C.successMuted, color: C.success }}
          >
            <IconSucces className="h-3.5 w-3.5" /> Lu
          </span>
        ) : (
          article.readingTimeMin && (
            <span
              className="inline-flex items-center gap-1 text-[11px] font-medium"
              style={{ color: C.grayFg }}
            >
              <IconTemps className="h-3.5 w-3.5" /> {article.readingTimeMin} min
            </span>
          )
        )}
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
      <span
        className="mt-4 text-[13px] font-semibold group-hover:underline"
        style={{ color: C.orange }}
      >
        {read ? 'Relire l’article →' : 'Lire l’article →'}
      </span>
    </Link>
  );
}
