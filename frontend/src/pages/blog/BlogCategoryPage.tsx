import { Link, useParams } from 'react-router';

import { ArticleCard } from '@/components/blog/ArticleCard';
import { getArticlesByCategory } from '@/content/blog/articles';
import { BLOG_CATEGORIES, categoryTone, getCategory } from '@/content/blog/categories';
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
        <h1 className="text-2xl" style={{ fontFamily: 'var(--font-serif)' }}>
          Catégorie introuvable
        </h1>
        <Link to="/blog" className="font-semibold hover:underline" style={{ color: C.orange }}>
          ← Retour au blog
        </Link>
      </div>
    );
  }

  const tone = categoryTone(category);
  const Icon = category.icon;
  const items = getArticlesByCategory(category.slug);
  const others = BLOG_CATEGORIES.filter((c) => c.slug !== category.slug);

  return (
    <div className="space-y-8">
      <Link to="/blog" className="text-[13px] hover:underline" style={{ color: C.grayFg }}>
        ← Tous les articles
      </Link>

      {/* En-tête du thème */}
      <header className="flex items-start gap-4">
        <span
          className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl"
          style={{ background: tone.soft, color: tone.fg }}
        >
          <Icon className="h-7 w-7" />
        </span>
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-[0.16em]" style={{ color: tone.fg }}>
            {category.stepLabel}
          </span>
          <h1
            className="mt-1 text-[clamp(1.7rem,3vw,2.3rem)] font-light leading-tight"
            style={{ fontFamily: 'var(--font-serif)', color: C.ink }}
          >
            {category.label}
          </h1>
          <p className="mt-2 max-w-2xl text-[15px] leading-relaxed" style={{ color: C.grayFg }}>
            {category.description}
          </p>
        </div>
      </header>

      {items.length > 0 ? (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((a) => (
            <ArticleCard key={a.slug} article={a} />
          ))}
        </div>
      ) : (
        <p style={{ color: C.grayFg }}>Aucun article dans cette catégorie pour le moment.</p>
      )}

      {/* Explorer les autres thèmes */}
      <div className="border-t pt-6" style={{ borderColor: C.border }}>
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.18em]" style={{ color: C.blue, opacity: 0.7 }}>
          Explorer les autres thèmes
        </p>
        <div className="flex flex-wrap gap-2.5">
          {others.map((c) => {
            const t = categoryTone(c);
            const CIcon = c.icon;
            return (
              <Link
                key={c.slug}
                to={`/blog/categorie/${c.slug}`}
                className="inline-flex items-center gap-2 rounded-full border px-3.5 py-2 text-[13px] font-medium transition-colors hover:bg-[var(--muted)]"
                style={{ borderColor: C.border, color: C.ink }}
              >
                <span className="flex h-5 w-5 items-center justify-center rounded-md" style={{ background: t.soft, color: t.fg }}>
                  <CIcon className="h-3.5 w-3.5" />
                </span>
                {c.stepLabel}
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
