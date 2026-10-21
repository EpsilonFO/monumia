import { useTranslation } from 'react-i18next';

import { cn } from '@/lib/utils';

import { changerLangue, LANGUES, langueCourante } from './index';

/**
 * Bascule de langue. Chaque langue est nommée dans sa propre langue (« English »
 * reste lisible pour qui ne lit pas le français). Le changement recharge la page.
 */
export function SelecteurLangue({ className }: { className?: string }) {
  const { t } = useTranslation();
  const courante = langueCourante();

  return (
    <div
      role="group"
      aria-label={t('langue.libelle')}
      className={cn('inline-flex items-center gap-1 text-sm', className)}
    >
      {LANGUES.map((langue, index) => (
        <span key={langue} className="inline-flex items-center gap-1">
          {index > 0 && (
            <span aria-hidden className="text-muted-foreground">
              ·
            </span>
          )}
          <button
            type="button"
            lang={langue}
            aria-pressed={langue === courante}
            disabled={langue === courante}
            onClick={() => changerLangue(langue)}
            className={cn(
              'rounded px-1 transition-colors',
              langue === courante
                ? 'font-medium text-foreground'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {t(`langue.${langue}`)}
          </button>
        </span>
      ))}
    </div>
  );
}
