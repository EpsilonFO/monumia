import { useTranslation } from 'react-i18next';
import { IconEquipe } from '@/components/icons';
import { C } from '@/lib/brand';

/** Étiquette « Partagé » dans l'identité de marque (bleu institutionnel). */
export function SharedBadge({ count }: { count?: number }) {
  const { t } = useTranslation('shell');
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[13px] font-semibold"
      style={{ background: C.paleBlue, color: C.blue }}
    >
      <IconEquipe className="h-3 w-3" strokeWidth={2} />
      {count && count > 0 ? t('SharedBadge.partageAvec', { count }) : t('SharedBadge.partage')}
    </span>
  );
}
