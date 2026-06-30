import { Link } from 'react-router';

import { ArticleCard } from '@/components/blog/ArticleCard';
import {
  getAllArticles,
  getArticlesByCategory,
} from '@/content/blog/articles';
import { BLOG_CATEGORIES } from '@/content/blog/categories';
import { C } from '@/lib/brand';
import { useDocumentMeta } from '@/hooks/useDocumentMeta';

export function BlogIndexPage() {
  useDocumentMeta(
    'Blog — Monumia',
    'Articles clairs pour comprendre la restauration du patrimoine, les aides et les démarches.',
  );
  const hasArticles = getAllArticles().length > 0;

  return (
    <div className="space-y-12">
      <section className="text-center">
        <h1
          className="text-[clamp(2rem,4vw,3rem)] font-light tracking-[-0.02em]"
          style={{ fontFamily: 'var(--font-serif)' }}
        >
          Comprendre le patrimoine, simplement
        </h1>
        <p className="mx-auto mt-3 max-w-2xl text-[15px]" style={{ color: '#6a7180' }}>
          Des articles clairs pour les propriétaires de monuments et les
          communes : statuts, aides, démarches et travaux.
        </p>
      </section>

      <nav className="flex flex-wrap justify-center gap-2">
        {BLOG_CATEGORIES.map((c) => (
          <Link
            key={c.slug}
            to={`/blog/categorie/${c.slug}`}
            className="rounded-full border bg-white px-4 py-1.5 text-[13px] font-medium hover:border-[color:var(--c-orange)]"
            style={{ borderColor: C.border, color: C.ink }}
          >
            {c.label}
          </Link>
        ))}
      </nav>

      {BLOG_CATEGORIES.map((category) => {
        const items = getArticlesByCategory(category.slug);
        if (items.length === 0) return null;
        return (
          <section key={category.slug} className="space-y-4">
            <div className="flex items-end justify-between">
              <h2
                className="text-[22px] font-normal"
                style={{ fontFamily: 'var(--font-serif)' }}
              >
                {category.label}
              </h2>
              <Link
                to={`/blog/categorie/${category.slug}`}
                className="text-[13px] font-semibold hover:underline"
                style={{ color: C.orange }}
              >
                Tout voir →
              </Link>
            </div>
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((a) => (
                <ArticleCard key={a.slug} article={a} />
              ))}
            </div>
          </section>
        );
      })}

      {!hasArticles && (
        <p className="text-center" style={{ color: '#6a7180' }}>
          Aucun article pour le moment.
        </p>
      )}
    </div>
  );
}
