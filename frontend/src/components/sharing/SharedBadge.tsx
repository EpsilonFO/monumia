import { IconEquipe } from '@/components/icons';
import { C } from '@/lib/brand';

/** Étiquette « Partagé » dans l'identité de marque (bleu institutionnel). */
export function SharedBadge({ count }: { count?: number }) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold"
      style={{ background: C.paleBlue, color: C.blue }}
    >
      <IconEquipe className="h-3 w-3" strokeWidth={2} />
      {count && count > 0 ? `Partagé · ${count} personne${count > 1 ? 's' : ''}` : 'Partagé'}
    </span>
  );
}
