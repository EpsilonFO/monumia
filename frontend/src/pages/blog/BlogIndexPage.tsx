import { Link } from 'react-router';

import { ArticleCard } from '@/components/blog/ArticleCard';
import { BandMotif } from '@/components/blog/BandMotif';
import { BlogParcoursNav } from '@/components/blog/BlogParcoursNav';
import { BlogSectionHeading } from '@/components/blog/BlogSectionHeading';
import { CategoryBadge } from '@/components/blog/CategoryBadge';
import { MonumiaCta } from '@/components/blog/MonumiaCta';
import type { BlogArticle } from '@/content/blog/articles';
import { getAllArticles, getArticlesByCategory } from '@/content/blog/articles';
import { BLOG_CATEGORIES, categoryTone, getCategory } from '@/content/blog/categories';
import { C } from '@/lib/brand';
import { IconSubvention, IconTemps } from '@/components/icons';
import { Clover } from '@/components/illustrations';
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
    <div className="space-y-10">
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

      {/* ─── FRISE DU PARCOURS (nav par thème, dans l'ordre du projet) ─── */}
      <BlogParcoursNav />

      {/* ─── ARTICLE À LA UNE ─── */}
      {featured && <FeaturedArticle article={featured} />}

      {/* ─── CORPS : sections 2 colonnes · rail droit d'infos ─── */}
      <div className="grid grid-cols-1 gap-x-10 gap-y-12 lg:grid-cols-[minmax(0,1fr)_16rem]">
        {/* Sections par thème (tous les liens dans le DOM → SEO) */}
        <div className="min-w-0 space-y-12">
          {BLOG_CATEGORIES.map((category, i) => {
            const items = getArticlesByCategory(category.slug).filter((a) => a.slug !== featured?.slug);
            if (items.length === 0) return null;
            const tone = categoryTone(category);
            const Icon = category.icon;
            return (
              // Chapitre coloré : panneau teinté du thème, icône fantôme, numéro d'étape.
              <section
                key={category.slug}
                id={`cat-${category.slug}`}
                className="relative overflow-hidden rounded-3xl p-5 scroll-mt-24 sm:p-7"
                style={{ background: tone.soft }}
              >
                <Icon
                  aria-hidden
                  className="absolute -bottom-9 -right-8 h-44 w-44 -rotate-6"
                  style={{ color: tone.fg, opacity: 0.06 }}
                />
                <div className="relative">
                  <BlogSectionHeading
                    eyebrow={category.stepLabel}
                    title={category.label}
                    numeral={`0${i + 1}`}
                    accent={tone.fg}
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
        <aside className="hidden lg:block">
          <div className="sticky top-24 space-y-6">
            {essentiels.length > 0 && (
              <section
                className="relative overflow-hidden rounded-2xl border p-5"
                style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' }}
              >
                <p
                  className="inline-flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em]"
                  style={{ color: C.blue }}
                >
                  <span aria-hidden style={{ width: 18, height: 2, borderRadius: 2, background: C.orange }} />
                  À lire en priorité
                </p>
                <ol className="mt-3.5 space-y-3.5">
                  {essentiels.map((a, i) => {
                    const cat = getCategory(a.categorySlug);
                    const tone = cat ? categoryTone(cat) : null;
                    return (
                      <li key={a.slug}>
                        <Link to={`/blog/article/${a.slug}`} className="group flex items-start gap-3">
                          <span
                            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[15px] font-bold"
                            style={{
                              fontFamily: 'var(--font-serif)',
                              background: tone?.soft ?? C.paleBlue,
                              color: tone?.fg ?? C.blue,
                            }}
                            aria-hidden
                          >
                            {i + 1}
                          </span>
                          <span className="min-w-0">
                            <span
                              className="block text-[13.5px] font-medium leading-snug group-hover:underline"
                              style={{ fontFamily: 'var(--font-serif)', color: C.ink }}
                            >
                              {a.title}
                            </span>
                            <span className="mt-0.5 block text-[11px]" style={{ color: C.grayMuted }}>
                              {cat?.shortLabel}
                              {a.readingTimeMin ? ` · ${a.readingTimeMin} min` : ''}
                            </span>
                          </span>
                        </Link>
                      </li>
                    );
                  })}
                </ol>
              </section>
            )}

            {/* Repère chiffré (rappel de la promesse produit) */}
            <section
              className="relative overflow-hidden rounded-2xl border p-5"
              style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' }}
            >
              <div className="flex items-center gap-3">
                <span
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
                  style={{ background: C.paleOrange, color: C.orange }}
                >
                  <IconSubvention className="h-5 w-5" />
                </span>
                <p className="text-[26px] font-bold leading-none tabular-nums" style={{ fontFamily: 'var(--font-serif)', color: C.orange }}>
                  150+
                </p>
              </div>
              <p className="mt-2.5 text-[12.5px] leading-relaxed" style={{ color: C.grayFg }}>
                aides au patrimoine référencées — nos articles vous aident à comprendre
                lesquelles vous concernent.
              </p>
            </section>

            {/* Accès Monumia (masqué si connecté) */}
            <MonumiaCta />
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
  const Icon = article.icon ?? category?.icon;
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
          <BandMotif
            slug={article.slug}
            className="absolute -right-4 bottom-0 h-24 w-auto opacity-[0.13]"
          />
          <Clover size={92} className="absolute -left-5 -top-6" style={{ color: tone.fg, opacity: 0.09 }} />
          <Icon className="relative h-24 w-24" />
        </div>
      )}
    </Link>
  );
}
