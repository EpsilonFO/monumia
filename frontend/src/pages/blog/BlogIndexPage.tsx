import { Link } from 'react-router';

import { ArticleCard } from '@/components/blog/ArticleCard';
import { BlogSectionHeading } from '@/components/blog/BlogSectionHeading';
import { CategoryBadge } from '@/components/blog/CategoryBadge';
import type { BlogArticle } from '@/content/blog/articles';
import { getAllArticles, getArticlesByCategory } from '@/content/blog/articles';
import { BLOG_CATEGORIES, categoryTone, getCategory } from '@/content/blog/categories';
import { C } from '@/lib/brand';
import { IconTemps } from '@/components/icons';
import { useDocumentMeta } from '@/hooks/useDocumentMeta';

function pubTime(a: BlogArticle): number {
  return a.publishedAt ? new Date(a.publishedAt).getTime() : 0;
}

export function BlogIndexPage() {
  useDocumentMeta(
    'Blog — Monumia',
    'Articles clairs pour comprendre la restauration du patrimoine, les aides et les démarches.',
  );

  const all = getAllArticles();
  const hasArticles = all.length > 0;
  const byRecent = [...all].sort((a, b) => pubTime(b) - pubTime(a));
  const featured = byRecent[0];
  const essentiels = byRecent.filter((a) => a.slug !== featured?.slug).slice(0, 4);

  return (
    <div className="space-y-12">
      {/* ─── EN-TÊTE (sobre, à la manière du tableau de bord) ─── */}
      <header>
        <span
          className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em]"
          style={{ color: C.blue }}
        >
          <span aria-hidden style={{ width: 22, height: 2, borderRadius: 2, background: C.orange }} />
          Le guide du patrimoine
        </span>
        <h1
          className="mt-3 text-[clamp(1.9rem,4vw,2.8rem)] font-light leading-[1.08] tracking-[-0.02em]"
          style={{ fontFamily: 'var(--font-serif)', color: C.ink }}
        >
          Comprendre le patrimoine, simplement
        </h1>
        <p className="mt-3 max-w-2xl text-[15px] leading-relaxed" style={{ color: C.grayFg }}>
          Des articles clairs pour les propriétaires de monuments et les communes :
          statuts, aides, démarches et travaux — sans jargon, à lire quand vous voulez.
        </p>
      </header>

      {/* ─── ARTICLE À LA UNE ─── */}
      {featured && <FeaturedArticle article={featured} />}

      {/* ─── CORPS ÉDITORIAL : rail gauche · articles · rail droit ─── */}
      <div className="grid grid-cols-1 gap-x-10 gap-y-12 lg:grid-cols-[12rem_minmax(0,1fr)] xl:grid-cols-[12rem_minmax(0,1fr)_16rem]">
        {/* Rail gauche : sommaire des thèmes (ancres) */}
        <aside className="hidden lg:block">
          <div className="sticky top-24 space-y-6">
            <nav aria-label="Thèmes du blog">
              <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.18em]" style={{ color: C.blue, opacity: 0.7 }}>
                Explorer par thème
              </p>
              <ul className="space-y-1">
                {BLOG_CATEGORIES.map((category) => {
                  const tone = categoryTone(category);
                  const count = getArticlesByCategory(category.slug).length;
                  if (count === 0) return null;
                  return (
                    <li key={category.slug}>
                      <a
                        href={`#cat-${category.slug}`}
                        className="group flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-[13px] transition-colors hover:bg-[var(--muted)]"
                        style={{ color: C.ink }}
                      >
                        <span aria-hidden className="h-2 w-2 shrink-0 rounded-full" style={{ background: tone.fg }} />
                        <span className="min-w-0 flex-1 truncate">{category.stepLabel}</span>
                        <span className="text-[11px] tabular-nums" style={{ color: C.grayMuted }}>{count}</span>
                      </a>
                    </li>
                  );
                })}
              </ul>
            </nav>
          </div>
        </aside>

        {/* Colonne centrale : sections par thème (tous les liens dans le DOM → SEO) */}
        <div className="min-w-0 space-y-12">
          {BLOG_CATEGORIES.map((category) => {
            const items = getArticlesByCategory(category.slug).filter((a) => a.slug !== featured?.slug);
            if (items.length === 0) return null;
            return (
              <section key={category.slug} id={`cat-${category.slug}`} className="scroll-mt-24">
                <BlogSectionHeading
                  eyebrow={category.stepLabel}
                  title={category.label}
                  action={
                    <Link
                      to={`/blog/categorie/${category.slug}`}
                      className="shrink-0 text-[13px] font-semibold hover:underline"
                      style={{ color: C.orange }}
                    >
                      Tout voir →
                    </Link>
                  }
                />
                <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                  {items.map((a) => (
                    <ArticleCard key={a.slug} article={a} />
                  ))}
                </div>
              </section>
            );
          })}

          {!hasArticles && (
            <p className="text-center" style={{ color: C.grayFg }}>
              Aucun article pour le moment.
            </p>
          )}
        </div>

        {/* Rail droit : sélection + repère chiffré + accès Monumia */}
        <aside className="hidden xl:block">
          <div className="sticky top-24 space-y-6">
            {essentiels.length > 0 && (
              <section
                className="rounded-2xl border p-5"
                style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' }}
              >
                <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.18em]" style={{ color: C.blue, opacity: 0.7 }}>
                  À lire en priorité
                </p>
                <ul className="space-y-3.5">
                  {essentiels.map((a) => {
                    const cat = getCategory(a.categorySlug);
                    const tone = cat ? categoryTone(cat) : null;
                    return (
                      <li key={a.slug}>
                        <Link to={`/blog/article/${a.slug}`} className="group flex gap-2.5">
                          {tone && <span aria-hidden className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ background: tone.fg }} />}
                          <span
                            className="text-[13.5px] font-medium leading-snug group-hover:underline"
                            style={{ fontFamily: 'var(--font-serif)', color: C.ink }}
                          >
                            {a.title}
                          </span>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </section>
            )}

            {/* Repère chiffré (rappel de la promesse produit) */}
            <section
              className="rounded-2xl border p-5"
              style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' }}
            >
              <p className="text-[26px] font-bold leading-none tabular-nums" style={{ fontFamily: 'var(--font-serif)', color: C.orange }}>
                150+
              </p>
              <p className="mt-1.5 text-[12.5px] leading-relaxed" style={{ color: C.grayFg }}>
                aides au patrimoine référencées — nos articles vous aident à comprendre
                lesquelles vous concernent.
              </p>
            </section>

            {/* Accès Monumia */}
            <section
              className="rounded-2xl border p-5"
              style={{ background: C.paleBlue, borderColor: C.border }}
            >
              <p className="text-[15px] font-semibold leading-snug" style={{ fontFamily: 'var(--font-serif)', color: C.blue }}>
                Un projet sur un bien protégé&nbsp;?
              </p>
              <p className="mt-2 text-[12.5px] leading-relaxed" style={{ color: C.ink, opacity: 0.72 }}>
                Monumia identifie votre statut et les aides mobilisables, et vous guide
                pas à pas.
              </p>
              <Link
                to="/login"
                className="group mt-4 inline-flex items-center gap-1.5 rounded-full px-4 py-2.5 text-[13px] font-semibold text-white transition-all duration-300 hover:-translate-y-0.5"
                style={{ background: C.orange, boxShadow: '0 10px 30px -8px rgba(241,113,5,0.55)' }}
              >
                Découvrir Monumia
                <span className="transition-transform duration-300 group-hover:translate-x-0.5">→</span>
              </Link>
            </section>
          </div>
        </aside>
      </div>
    </div>
  );
}

/** Article mis en avant : carte large, texte + panneau décoratif teinté (icône du thème, sans photo). */
function FeaturedArticle({ article }: { article: BlogArticle }) {
  const category = getCategory(article.categorySlug);
  const tone = category ? categoryTone(category) : null;
  const Icon = category?.icon;
  return (
    <Link
      to={`/blog/article/${article.slug}`}
      className="group grid overflow-hidden rounded-3xl border transition-all duration-300 hover:-translate-y-0.5 sm:grid-cols-[1.5fr_1fr]"
      style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' }}
    >
      <div className="flex flex-col justify-center p-7 sm:p-9">
        <div className="flex flex-wrap items-center gap-3">
          {category && <CategoryBadge category={category} />}
          <span className="text-[11px] font-semibold uppercase tracking-[0.16em]" style={{ color: C.orange }}>
            À la une
          </span>
        </div>
        <h2
          className="mt-3 text-[clamp(1.4rem,2.6vw,2rem)] font-normal leading-[1.12] tracking-[-0.01em]"
          style={{ fontFamily: 'var(--font-serif)', color: C.ink }}
        >
          {article.title}
        </h2>
        <p className="mt-3 max-w-xl text-[14px] leading-relaxed" style={{ color: C.grayFg }}>
          {article.excerpt}
        </p>
        <div className="mt-5 flex items-center gap-4">
          <span className="text-[13px] font-semibold group-hover:underline" style={{ color: C.orange }}>
            Lire l’article →
          </span>
          {article.readingTimeMin && (
            <span className="inline-flex items-center gap-1 text-[12px] font-medium" style={{ color: C.grayMuted }}>
              <IconTemps className="h-3.5 w-3.5" /> {article.readingTimeMin} min
            </span>
          )}
        </div>
      </div>
      {tone && Icon && (
        <div
          aria-hidden
          className="relative hidden items-center justify-center overflow-hidden sm:flex"
          style={{ background: tone.soft, color: tone.fg }}
        >
          <span className="absolute -right-6 -top-6 h-28 w-28 rounded-full" style={{ background: tone.fg, opacity: 0.1 }} />
          <span className="absolute -bottom-8 -left-4 h-24 w-24 rounded-full" style={{ background: tone.fg, opacity: 0.1 }} />
          <Icon className="relative h-24 w-24" />
        </div>
      )}
    </Link>
  );
}
