import { Link } from 'react-router';

import { ArticleCard } from '@/components/blog/ArticleCard';
import { ParcoursCard } from '@/components/blog/ParcoursCard';
import { BlogSectionHeading } from '@/components/blog/BlogSectionHeading';
import {
  getAllArticles,
  getArticlesByCategory,
  nextUnread,
} from '@/content/blog/articles';
import { BLOG_CATEGORIES } from '@/content/blog/categories';
import { C } from '@/lib/brand';
import { useReadArticles } from '@/components/blog/useReadArticles';
import { useDocumentMeta } from '@/hooks/useDocumentMeta';

export function BlogIndexPage() {
  useDocumentMeta(
    'Blog — Monumia',
    'Articles clairs pour comprendre la restauration du patrimoine, les aides et les démarches.',
  );

  const all = getAllArticles();
  const hasArticles = all.length > 0;
  const { readSlugs, countRead } = useReadArticles();
  const readCount = countRead(all.map((a) => a.slug));
  const resume = nextUnread(all, readSlugs);
  const started = readCount > 0;
  const pct = all.length > 0 ? Math.round((readCount / all.length) * 100) : 0;

  return (
    <div className="space-y-12">
      {/* ─── HERO ─── */}
      <section>
        <span
          className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em]"
          style={{ color: C.blue }}
        >
          <span aria-hidden style={{ width: 22, height: 2, borderRadius: 2, background: C.orange }} />
          Le guide du patrimoine
        </span>
        <h1
          className="mt-3 text-[clamp(2rem,4vw,3rem)] font-light tracking-[-0.02em]"
          style={{ fontFamily: 'var(--font-serif)', color: C.ink }}
        >
          Comprendre le patrimoine, pas à pas
        </h1>
        <p className="mt-3 max-w-2xl text-[15px]" style={{ color: C.grayFg }}>
          Des repères clairs pour les propriétaires de monuments et les communes :
          statuts, aides, démarches et travaux. Avancez à votre rythme —
          {' '}on garde le fil pour vous.
        </p>

        {/* Progression globale (si déjà commencé) */}
        {started && (
          <div
            className="mt-6 flex flex-col gap-2 rounded-2xl border p-4 sm:flex-row sm:items-center sm:justify-between"
            style={{ background: C.card, borderColor: C.border }}
          >
            <div className="min-w-0">
              <p className="text-[13px] font-semibold" style={{ color: C.ink }}>
                Vous avez lu {readCount} des {all.length} repères — continuez&nbsp;!
              </p>
              <div
                className="mt-2 h-1.5 w-full max-w-xs overflow-hidden rounded-full"
                style={{ background: C.border }}
                role="progressbar"
                aria-valuenow={pct}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`Progression globale : ${readCount} sur ${all.length} repères lus`}
              >
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${pct}%`, background: C.orange }}
                />
              </div>
            </div>
            {resume && (
              <Link
                to={`/blog/article/${resume.slug}`}
                className="inline-flex shrink-0 items-center gap-1.5 rounded-full px-4 py-2.5 text-[13px] font-semibold text-white transition-transform duration-300 hover:-translate-y-0.5"
                style={{ background: C.orange }}
              >
                Reprendre la lecture
                <span>→</span>
              </Link>
            )}
          </div>
        )}
      </section>

      {/* ─── PARCOURS ─── */}
      <section>
        <BlogSectionHeading
          eyebrow="Par où commencer"
          title="Choisissez votre parcours"
        />
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          {BLOG_CATEGORIES.map((category) => (
            <ParcoursCard key={category.slug} category={category} />
          ))}
        </div>
      </section>

      {/* ─── SECTIONS PAR CATÉGORIE (tous les liens dans le DOM) ─── */}
      {BLOG_CATEGORIES.map((category) => {
        const items = getArticlesByCategory(category.slug);
        if (items.length === 0) return null;
        return (
          <section key={category.slug}>
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
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
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
  );
}
