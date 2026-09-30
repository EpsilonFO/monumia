import { useState } from 'react';
import { IconInfo } from '@/components/icons';
import { C } from '@/lib/brand';
import { cn } from '@/lib/utils';

/**
 * Au-delà, le texte d'aide est replié à trois lignes. Seuil calé sur la largeur
 * de lecture (62ch) : les textes courts s'affichent en entier, les longs (la
 * moitié de l'ontologie dépasse 190 caractères) ne poussent pas les réponses
 * sous la ligne de flottaison.
 */
const HELP_CLAMP_CHARS = 170;

/**
 * Note explicative d'une question : encart distinct de la question elle-même,
 * en contraste lisible, replié à trois lignes quand il est long. Même geste que
 * « Lire la suite » sur la fiche d'aide.
 */
export function QuestionHelp({ text, compact }: { text: string; compact?: boolean }) {
  const [open, setOpen] = useState(false);
  const long = text.length > HELP_CLAMP_CHARS;
  return (
    <div
      className={cn(
        'flex max-w-[62ch] gap-2.5 rounded-xl border-l-[3px]',
        compact ? 'py-2 pl-2.5 pr-3' : 'py-2.5 pl-3 pr-3.5',
      )}
      style={{ borderColor: C.blueLight, background: 'var(--secondary)' }}
    >
      <IconInfo className="mt-[3px] h-4 w-4 shrink-0" style={{ color: C.blue }} />
      <div className="min-w-0">
        <p
          className={cn(
            'leading-relaxed',
            compact ? 'text-[15px]' : 'text-[16px]',
            !open && long && 'line-clamp-3',
          )}
          style={{ color: C.grayFg }}
        >
          {text}
        </p>
        {long && (
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className="mt-1 text-[15px] font-semibold underline-offset-2 hover:underline"
            style={{ color: C.blue }}
          >
            {open ? 'Réduire' : 'Lire la suite'}
          </button>
        )}
      </div>
    </div>
  );
}
