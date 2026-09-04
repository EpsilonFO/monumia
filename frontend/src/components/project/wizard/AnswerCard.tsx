import { Check } from 'lucide-react';
import { IconHelp } from '@/components/icons';
import { C } from '@/lib/brand';
import { cn } from '@/lib/utils';
import type { QcmOption } from '@/types';
import { isUnknownAnswer } from './unknownAnswer';

interface AnswerCardProps {
  option: QcmOption;
  selected: boolean;
  /** Roving tabindex : seul l'élément « actif » du radiogroup est tabbable. */
  roving: boolean;
  /** Question à choix multiple : case à cocher (carrée) plutôt que radio. */
  multiple?: boolean;
  onSelect: () => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLButtonElement>) => void;
  buttonRef: (el: HTMLButtonElement | null) => void;
}

/**
 * Carte-réponse du questionnaire : la coche à gauche, le libellé ensuite —
 * même grammaire que les tuiles des écrans de cadrage (`CadrageTile`), pour
 * que le parcours se lise d'un bout à l'autre comme une seule séquence. La
 * forme de la coche porte à elle seule le mode de réponse : ronde en choix
 * simple, carrée en choix multiple, avant même le premier clic. Hover = léger
 * lift + ombre pop ; sélection = bordure accent + fond orange pâle.
 */
export function AnswerCard({
  option,
  selected,
  roving,
  multiple,
  onSelect,
  onKeyDown,
  buttonRef,
}: AnswerCardProps) {
  // Filet : les « je ne sais pas » passent normalement par SkipCard, mais s'ils
  // atterrissent ici ils ne doivent pas se lire comme une réponse de plein droit.
  const unknown = isUnknownAnswer(option);

  return (
    <button
      ref={buttonRef}
      type="button"
      role={multiple ? 'checkbox' : 'radio'}
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
      style={{ color: unknown ? C.grayFg : C.ink }}
    >
      <span
        aria-hidden
        className={cn(
          'flex h-6 w-6 shrink-0 items-center justify-center border-2 transition-colors',
          multiple ? 'rounded-md' : 'rounded-full',
          selected
            ? 'border-accent bg-accent text-white'
            : 'border-border group-hover:border-warning',
        )}
      >
        {selected && <Check className="h-3.5 w-3.5" strokeWidth={3} />}
      </span>
      {unknown && <IconHelp aria-hidden className="h-4 w-4 shrink-0" />}
      <span className="flex-1">{option.label}</span>
    </button>
  );
}
