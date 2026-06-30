import { Link, useParams } from 'react-router';

import { ArticleCard } from '@/components/blog/ArticleCard';
import { getArticlesByCategory } from '@/content/blog/articles';
import { getCategory } from '@/content/blog/categories';
import { C } from '@/lib/brand';
import { useDocumentMeta } from '@/hooks/useDocumentMeta';

export function BlogCategoryPage() {
  const { categorySlug } = useParams();
  const category = categorySlug ? getCategory(categorySlug) : undefined;

  useDocumentMeta(
    category ? `${category.label} — Blog Monumia` : 'Catégorie introuvable',
    category?.description,
  );

  if (!category) {
    return (
      <div className="space-y-4 text-center">
        <h1
          className="text-2xl"
          style={{ fontFamily: 'var(--font-serif)' }}
        >
          Catégorie introuvable
        </h1>
        <Link
          to="/blog"
          className="font-semibold hover:underline"
          style={{ color: C.orange }}
        >
          ← Retour au blog
        </Link>
      </div>
    );
  }

  const items = getArticlesByCategory(category.slug);
  return (
    <div className="space-y-8">
      <Link to="/blog" className="text-[13px] hover:underline" style={{ color: '#6a7180' }}>
        ← Tous les articles
      </Link>
      <header className="space-y-2">
        <h1
          className="text-[clamp(1.8rem,3vw,2.4rem)] font-light"
          style={{ fontFamily: 'var(--font-serif)' }}
        >
          {category.label}
        </h1>
        <p className="max-w-2xl text-[15px]" style={{ color: '#6a7180' }}>
          {category.description}
        </p>
      </header>
      {items.length > 0 ? (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((a) => (
            <ArticleCard key={a.slug} article={a} />
          ))}
        </div>
      ) : (
        <p style={{ color: '#6a7180' }}>
          Aucun article dans cette catégorie pour le moment.
        </p>
      )}
    </div>
  );
}
