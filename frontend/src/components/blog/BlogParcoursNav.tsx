import { useTranslation } from 'react-i18next';

import { getArticlesByCategory } from '@/content/blog/articles';
import { BLOG_CATEGORIES, categoryTone } from '@/content/blog/categories';
import { C } from '@/lib/brand';

/**
 * Frise du parcours propriétaire : les 4 thèmes du blog forment une vraie
 * séquence (statut → aides → dossier → travaux), d’où la numérotation.
 * Chaque étape renvoie à sa section de l’index (ancre `#cat-<slug>`) ;
 * une étape sans article est affichée mais inactive.
 */
export function BlogParcoursNav() {
  const { t } = useTranslation('blog');
  return (
    <nav aria-label={t('BlogParcoursNav.ariaParcours')}>
      <ol className="flex items-stretch gap-3 overflow-x-auto pb-1">
        {BLOG_CATEGORIES.map((category, i) => {
          const tone = categoryTone(category);
          const Icon = category.icon;
          const count = getArticlesByCategory(category.slug).length;
          const isLast = i === BLOG_CATEGORIES.length - 1;

          const content = (
            <>
              <span
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
                style={{ background: C.card, color: tone.fg }}
              >
                <Icon className="h-5 w-5" />
              </span>
              <span className="min-w-0">
                <span
                  className="block text-[12px] font-semibold uppercase tracking-[0.16em]"
                  style={{ color: tone.fg }}
                >
                  {t('BlogParcoursNav.etape', { numero: i + 1 })}
                </span>
                <span
                  className="block whitespace-nowrap text-[15.5px] font-medium leading-tight"
                  style={{ color: C.ink }}
                >
                  {category.stepLabel}
                </span>
                <span className="block text-[13px]" style={{ color: C.grayMuted }}>
                  {count > 0
                    ? t('BlogParcoursNav.articles', { count })
                    : t('BlogParcoursNav.bientot')}
                </span>
              </span>
            </>
          );

          return (
            <li key={category.slug} className="flex min-w-[14rem] flex-1 items-center gap-3">
              {count > 0 ? (
                <a
                  href={`#cat-${category.slug}`}
                  className="flex flex-1 items-center gap-3 rounded-2xl p-3 transition-all duration-300 hover:-translate-y-0.5"
                  style={{ background: tone.soft, boxShadow: 'var(--shadow-card)' }}
                >
                  {content}
                </a>
              ) : (
                <div
                  className="flex flex-1 items-center gap-3 rounded-2xl border border-dashed p-3 opacity-60"
                  style={{ borderColor: C.border }}
                >
                  {content}
                </div>
              )}
              {!isLast && (
                <span
                  aria-hidden
                  className="hidden w-4 shrink-0 border-t-2 border-dashed lg:block"
                  style={{ borderColor: C.orange, opacity: 0.45 }}
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
