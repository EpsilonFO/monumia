import { C } from '@/lib/brand';
import { cn } from '@/lib/utils';

interface SkipCardProps {
  label: string;
  /** Vraie option du moteur (« je ne sais pas ») plutôt que le simple « passer ». */
  asOption?: boolean;
  selected?: boolean;
  /** Roving tabindex : seul l'élément « actif » du radiogroup est tabbable. */
  roving?: boolean;
  /** Question à choix multiple : l'option est une case à cocher. */
  multiple?: boolean;
  onSelect: () => void;
  onKeyDown?: (e: React.KeyboardEvent<HTMLButtonElement>) => void;
  buttonRef?: (el: HTMLButtonElement | null) => void;
}

/**
 * Échappatoire d'une question : « Passer cette question » et les options « je
 * ne sais pas » du moteur portent la même forme — pleine largeur, sans fond,
 * bordure pointillée. Ce n'est pas une réponse comme les autres, et ça doit se
 * voir de la même façon partout dans le questionnaire.
 */
export function SkipCard({
  label,
  asOption,
  selected,
  roving,
  multiple,
  onSelect,
  onKeyDown,
  buttonRef,
}: SkipCardProps) {
  return (
    <button
      ref={buttonRef}
      type="button"
      role={asOption ? (multiple ? 'checkbox' : 'radio') : undefined}
      aria-checked={asOption ? !!selected : undefined}
      tabIndex={asOption ? (roving ? 0 : -1) : undefined}
      onClick={onSelect}
      onKeyDown={onKeyDown}
      className={cn(
        'w-full rounded-2xl border border-dashed px-5 py-3 text-[14px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        selected ? 'border-accent bg-warning-muted' : 'hover:border-warning hover:bg-warning-muted',
      )}
      style={selected ? { color: C.ink } : { borderColor: C.border, color: C.grayFg }}
    >
      {label}
    </button>
  );
}
