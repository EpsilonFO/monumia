import { Check } from 'lucide-react';
import { C } from '@/lib/brand';
import { cn } from '@/lib/utils';
import type { QcmOption } from '@/types';
import { iconForOption } from './iconForOption';

const LETTERS = 'ABCDEFGHIJKL';

// Tuiles d'icônes : le duo de marque décliné — les bleus (monument,
// information) alternent avec les oranges (action). Cyclé par position,
// la sélection reste orange plein.
const TILE_TONES = [
  { bg: 'var(--secondary)', fg: 'var(--primary)' },
  { bg: 'var(--warning-muted)', fg: 'var(--accent)' },
  { bg: 'var(--info-muted)', fg: 'var(--info)' },
  { bg: 'color-mix(in srgb, var(--orange-vif) 16%, #fff)', fg: 'var(--orange-vif)' },
] as const;

interface AnswerCardProps {
  option: QcmOption;
  optionIndex: number;
  selected: boolean;
  /** Roving tabindex : seul l'élément « actif » du radiogroup est tabbable. */
  roving: boolean;
  onSelect: () => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLButtonElement>) => void;
  buttonRef: (el: HTMLButtonElement | null) => void;
}

/**
 * Carte-réponse du questionnaire : tuile d'icône illustrative (heuristique
 * mots-clés, pastille lettrée en repli), libellé, coche à droite. Hover =
 * léger lift + ombre pop ; sélection = bordure accent + fond orange pâle.
 */
export function AnswerCard({
  option,
  optionIndex,
  selected,
  roving,
  onSelect,
  onKeyDown,
  buttonRef,
}: AnswerCardProps) {
  const Icon = iconForOption(option);
  const tile = TILE_TONES[optionIndex % TILE_TONES.length];

  return (
    <button
      ref={buttonRef}
      type="button"
      role="radio"
      aria-checked={selected}
      tabIndex={roving ? 0 : -1}
      onClick={onSelect}
      onKeyDown={onKeyDown}
      className={cn(
        'group flex min-h-[3.5rem] w-full items-center gap-3.5 rounded-2xl border-2 px-4 py-2.5 text-left text-[15px] font-medium leading-snug transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        selected
          ? 'border-accent bg-warning-muted shadow-[var(--shadow-card)]'
          : 'border-border bg-card hover:-translate-y-0.5 hover:border-warning hover:shadow-[var(--shadow-pop)]',
      )}
      style={{ color: C.ink }}
    >
      <span
        aria-hidden
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-colors"
        style={
          selected
            ? { background: C.orange, color: '#fff' }
            : { background: tile.bg, color: tile.fg }
        }
      >
        {Icon ? (
          <Icon className="h-5 w-5" />
        ) : (
          <span className="text-[14px] font-bold">{LETTERS[optionIndex] ?? '•'}</span>
        )}
      </span>
      <span className="flex-1">{option.label}</span>
      <span
        aria-hidden
        className={cn(
          'flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 transition-colors',
          selected ? 'border-accent bg-accent text-white' : 'border-border',
        )}
      >
        {selected ? (
          <Check className="h-3.5 w-3.5" strokeWidth={3} />
        ) : (
          <span className="h-1.5 w-1.5 rounded-full bg-muted transition-colors group-hover:bg-accent" />
        )}
      </span>
    </button>
  );
}
