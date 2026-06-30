import { Link } from 'react-router';

import type { BlogArticle } from '@/content/blog/articles';
import { getCategory } from '@/content/blog/categories';
import { C } from '@/lib/brand';
import { CategoryBadge } from './CategoryBadge';

export function ArticleCard({ article }: { article: BlogArticle }) {
  const category = getCategory(article.categorySlug);
  return (
    <Link
      to={`/blog/article/${article.slug}`}
      className="group flex flex-col rounded-2xl border p-5 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_24px_50px_-28px_rgba(7,42,114,0.5)]"
      style={{ background: C.card, borderColor: C.border }}
    >
      {category && <CategoryBadge category={category} />}
      <h3
        className="mt-3 text-[19px] font-normal leading-snug"
        style={{ fontFamily: 'var(--font-serif)', color: C.ink }}
      >
        {article.title}
      </h3>
      <p className="mt-2 line-clamp-3 text-[13px] leading-relaxed" style={{ color: '#6a7180' }}>
        {article.excerpt}
      </p>
      <span
        className="mt-4 text-[13px] font-semibold group-hover:underline"
        style={{ color: C.orange }}
      >
        Lire l’article →
      </span>
    </Link>
  );
}
