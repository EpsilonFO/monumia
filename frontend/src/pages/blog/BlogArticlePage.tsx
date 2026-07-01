import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router';

import { CategoryBadge } from '@/components/blog/CategoryBadge';
import { MarkdownArticle } from '@/components/blog/markdown/MarkdownArticle';
import { Toc } from '@/components/blog/markdown/Toc';
import { useReadArticles } from '@/components/blog/useReadArticles';
import {
  getAllArticles,
  getArticleBySlug,
  getArticlesByCategory,
  nextUnread,
} from '@/content/blog/articles';
import { getCategory } from '@/content/blog/categories';
import { C } from '@/lib/brand';
import { IconSucces, IconTemps } from '@/components/icons';
import { useDocumentMeta } from '@/hooks/useDocumentMeta';

export function BlogArticlePage() {
  const { slug } = useParams();
  const article = slug ? getArticleBySlug(slug) : undefined;
  const [loaded, setLoaded] = useState<{ slug: string; md: string } | null>(null);
  const body = article && loaded?.slug === article.slug ? loaded.md : '';

  const { readSlugs, isRead, markRead } = useReadArticles();
  const [progress, setProgress] = useState(0);

  useDocumentMeta(
    article ? `${article.title} — Blog Monumia` : 'Article introuvable',
    article?.excerpt,
  );

  useEffect(() => {
    let active = true;
    if (article) {
      article.body().then((md) => {
        if (active) setLoaded({ slug: article.slug, md });
      });
    }
    return () => {
      active = false;
    };
  }, [article]);

  // Progression de lecture (scroll de la fenêtre) + marquage « lu » à 70 %.
  const markedRef = useRef(false);
  useEffect(() => {
    markedRef.current = false;
    setProgress(0);
  }, [article]);
  useEffect(() => {
    function onScroll() {
      const doc = document.documentElement;
      const max = doc.scrollHeight - doc.clientHeight;
      const ratio = max > 0 ? Math.min(1, doc.scrollTop / max) : 0;
      setProgress(ratio);
      if (article && !markedRef.current && ratio >= 0.7) {
        markedRef.current = true;
        markRead(article.slug);
      }
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener('scroll', onScroll);
  }, [article, markRead]);

  if (!article) {
    return (
      <div className="space-y-4 text-center">
        <h1 className="text-2xl" style={{ fontFamily: 'var(--font-serif)' }}>
          Article introuvable
        </h1>
        <Link to="/blog" className="font-semibold hover:underline" style={{ color: C.orange }}>
          ← Retour au blog
        </Link>
      </div>
    );
  }

  const category = getCategory(article.categorySlug);
  const read = isRead(article.slug);
  const related = getArticlesByCategory(article.categorySlug)
    .filter((a) => a.slug !== article.slug)
    .slice(0, 3);
  // Étape suivante : 1er non-lu du parcours courant, sinon 1er non-lu global.
  const nextStep =
    nextUnread(
      getArticlesByCategory(article.categorySlug).filter((a) => a.slug !== article.slug),
      readSlugs,
    ) ?? nextUnread(getAllExceptCurrent(article.slug), readSlugs);

  return (
    <article>
      {/* Barre de progression de lecture (collante) */}
      <div
        className="fixed inset-x-0 top-0 z-40 h-1"
        style={{ background: 'transparent' }}
        aria-hidden
      >
        <div
          className="h-full transition-[width] duration-150"
          style={{ width: `${Math.round(progress * 100)}%`, background: C.orange }}
        />
      </div>

      {/* Fil d'ariane */}
      <nav className="text-[12.5px]" style={{ color: C.grayFg }} aria-label="Fil d'ariane">
        <Link to="/blog" className="hover:underline">
          Blog
        </Link>
        {category && (
          <>
            {' › '}
            <Link to={`/blog/categorie/${category.slug}`} className="hover:underline">
              {category.label}
            </Link>
          </>
        )}
      </nav>

      {/* En-tête */}
      <header className="mt-4 max-w-3xl">
        <div className="flex flex-wrap items-center gap-3">
          {category && <CategoryBadge category={category} asLink />}
          {article.readingTimeMin && (
            <span
              className="inline-flex items-center gap-1 text-[12px] font-semibold"
              style={{ color: C.grayFg }}
            >
              <IconTemps className="h-3.5 w-3.5" /> {article.readingTimeMin} min de lecture
            </span>
          )}
          {read && (
            <span
              className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[12px] font-semibold"
              style={{ background: C.successMuted, color: C.success }}
            >
              <IconSucces className="h-3.5 w-3.5" /> Déjà lu
            </span>
          )}
        </div>
        <h1
          className="mt-3 text-[clamp(1.9rem,3.6vw,2.7rem)] font-normal leading-[1.12] tracking-[-0.01em]"
          style={{ fontFamily: 'var(--font-serif)', color: C.ink }}
        >
          {article.title}
        </h1>
        <p className="mt-3 text-[16px] leading-relaxed" style={{ color: C.grayFg }}>
          {article.excerpt}
        </p>
        <div className="mt-5 h-px w-full" style={{ background: C.border }} />
      </header>

      {/* Grille 3 colonnes */}
      <div className="mt-8 grid grid-cols-1 gap-x-10 gap-y-10 lg:grid-cols-[13rem_minmax(0,1fr)] xl:grid-cols-[13rem_minmax(0,1fr)_15rem]">
        <aside className="hidden lg:block">
          <div className="sticky top-24">{body && <Toc body={body} />}</div>
        </aside>

        <div className="min-w-0 max-w-2xl">
          <MarkdownArticle body={body} />

          {/* Encart « étape suivante » */}
          {nextStep && (
            <div
              className="mt-10 rounded-2xl border p-5"
              style={{ background: C.successMuted, borderColor: C.border }}
            >
              <p
                className="inline-flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-[0.14em]"
                style={{ color: C.success }}
              >
                <IconSucces className="h-4 w-4" /> Repère acquis — étape suivante
              </p>
              <Link
                to={`/blog/article/${nextStep.slug}`}
                className="group mt-2 block text-[18px] font-normal leading-snug hover:underline"
                style={{ fontFamily: 'var(--font-serif)', color: C.ink }}
              >
                {nextStep.title}
                <span className="ml-1 inline-block transition-transform duration-300 group-hover:translate-x-0.5" style={{ color: C.orange }}>
                  →
                </span>
              </Link>
            </div>
          )}
        </div>

        {/* Rail droit */}
        <aside className="flex flex-col gap-6 xl:max-w-[15rem]" aria-label="Pour aller plus loin">
          <div className="sticky top-24 flex flex-col gap-6">
            {related.length > 0 && (
              <section>
                <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: C.blue, opacity: 0.55 }}>
                  À lire aussi
                </p>
                <div className="flex flex-col gap-3">
                  {related.map((a) => {
                    const cat = getCategory(a.categorySlug);
                    return (
                      <Link
                        key={a.slug}
                        to={`/blog/article/${a.slug}`}
                        className="group block rounded-xl border p-4 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_18px_40px_-24px_rgba(7,42,114,0.55)]"
                        style={{ background: C.card, borderColor: C.border }}
                      >
                        {cat && (
                          <span className="text-[10px] font-semibold uppercase tracking-[0.14em]" style={{ color: C.orange }}>
                            {cat.label}
                          </span>
                        )}
                        <span className="mt-1.5 block text-[14.5px] font-medium leading-snug" style={{ fontFamily: 'var(--font-serif)', color: C.ink }}>
                          {a.title}
                        </span>
                        <span className="mt-2.5 inline-flex items-center gap-1 text-[12px] font-semibold" style={{ color: C.orange }}>
                          Lire
                          <span className="transition-transform duration-300 group-hover:translate-x-0.5">→</span>
                        </span>
                      </Link>
                    );
                  })}
                </div>
              </section>
            )}

            {/* CTA Monumia */}
            <section className="relative overflow-hidden rounded-2xl border p-5" style={{ background: C.paleBlue, borderColor: C.border }}>
              <p className="text-[16px] font-semibold leading-snug" style={{ fontFamily: 'var(--font-serif)', color: C.blue }}>
                Un projet sur un bien protégé&nbsp;?
              </p>
              <p className="mt-2 text-[12.5px] leading-relaxed" style={{ color: C.grayFg }}>
                Monumia identifie votre statut et les aides mobilisables, et vous guide dans vos démarches.
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
    </article>
  );
}

/** Tous les articles sauf l'article courant, dans l'ordre du trajet (parcours). */
function getAllExceptCurrent(currentSlug: string) {
  return getAllArticles().filter((a) => a.slug !== currentSlug);
}
