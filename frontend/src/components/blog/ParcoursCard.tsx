import { Link } from 'react-router';

import { type BlogCategory, categoryTone } from '@/content/blog/categories';
import { getArticlesByCategory, nextUnread } from '@/content/blog/articles';
import { C } from '@/lib/brand';
import { useReadArticles } from './useReadArticles';

/**
 * Carte d'un parcours (= une catégorie). Affiche la progression de lecture et un
 * CTA « Commencer / Continuer / Revoir le parcours ». Le clic sur la carte navigue
 * (SPA) vers le premier article non lu quand un parcours est en cours, sinon vers
 * la page de la catégorie.
 */
export function ParcoursCard({
  category,
  size = 'grid',
}: {
  category: BlogCategory;
  size?: 'grid' | 'hero';
}) {
  const { readSlugs, countRead } = useReadArticles();
  const articles = getArticlesByCategory(category.slug);
  const total = articles.length;
  const read = countRead(articles.map((a) => a.slug));
  const tone = categoryTone(category);
  const Icon = category.icon;
  const next = nextUnread(articles, readSlugs);
  const done = total > 0 && read === total;
  const pct = total > 0 ? Math.round((read / total) * 100) : 0;

  const ctaTo =
    !done && next ? `/blog/article/${next.slug}` : `/blog/categorie/${category.slug}`;
  const ctaLabel = done ? 'Revoir le parcours' : read > 0 ? 'Continuer' : 'Commencer';

  return (
    <Link
      to={ctaTo}
      className="group relative flex flex-col overflow-hidden rounded-2xl border p-5 pt-6 transition-all duration-300 hover:-translate-y-0.5"
      style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' }}
    >
      <span aria-hidden className="absolute inset-x-0 top-0 h-1.5" style={{ background: tone.fg }} />
      <div className="flex items-center gap-3">
        <span
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl"
          style={{ background: tone.soft, color: tone.fg }}
        >
          <Icon className="h-6 w-6" />
        </span>
        <div className="min-w-0">
          <h3
            className={`${size === 'hero' ? 'text-[22px]' : 'text-[18px]'} font-normal leading-tight`}
            style={{ fontFamily: 'var(--font-serif)', color: C.ink }}
          >
            {category.stepLabel}
          </h3>
          <p className="text-[12px]" style={{ color: C.grayFg }}>
            {total} article{total > 1 ? 's' : ''}
          </p>
        </div>
      </div>

      <p className="mt-3 line-clamp-2 text-[13px] leading-relaxed" style={{ color: C.grayFg }}>
        {category.description}
      </p>

      {/* Progression */}
      <div className="mt-4">
        <div className="flex items-center justify-between text-[11px] font-semibold">
          <span style={{ color: done ? C.success : C.grayFg }}>
            {done ? 'Parcours terminé ✓' : `${read} sur ${total} lus`}
          </span>
        </div>
        <div
          className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full"
          style={{ background: C.border }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Progression du parcours : ${read} sur ${total} articles lus`}
        >
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{ width: `${pct}%`, background: done ? C.success : tone.fg }}
          />
        </div>
      </div>

      {/* CTA */}
      <span
        className="mt-4 inline-flex w-fit items-center gap-1.5 text-[13px] font-semibold group-hover:underline"
        style={{ color: C.orange }}
      >
        {ctaLabel}
        <span className="transition-transform duration-300 group-hover:translate-x-0.5">→</span>
      </span>
    </Link>
  );
}
