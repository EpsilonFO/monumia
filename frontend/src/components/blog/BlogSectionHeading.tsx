import type { ReactNode } from 'react';
import { C } from '@/lib/brand';

/**
 * En-tête de section éditorial du blog : filet + eyebrow + titre serif,
 * avec en option un numéro de chapitre fantôme et une teinte de catégorie
 * (par défaut : filet orange / eyebrow bleu, comme le reste du site).
 */
export function BlogSectionHeading({
  eyebrow,
  title,
  action,
  numeral,
  accent,
}: {
  eyebrow: string;
  title: string;
  action?: ReactNode;
  /** Numéro de chapitre affiché en fantôme devant le titre (ex. « 01 »). */
  numeral?: string;
  /** Couleur d'accent (filet + eyebrow + numéro) — ex. `tone.fg` de la catégorie. */
  accent?: string;
}) {
  return (
    <div className="mb-4 flex items-end justify-between gap-4">
      <div>
        <span
          className="inline-flex items-center gap-2 text-[12px] font-semibold uppercase tracking-[0.18em]"
          style={{ color: accent ?? C.blue }}
        >
          <span aria-hidden style={{ width: 20.5, height: 2, borderRadius: 2, background: accent ?? C.orange }} />
          {eyebrow}
        </span>
        <h2
          className="mt-1.5 flex items-baseline gap-2.5 text-[clamp(1.15rem,2vw,1.5rem)] leading-tight"
          style={{ fontFamily: 'var(--font-serif)', color: C.ink }}
        >
          {numeral && (
            <span
              aria-hidden
              className="text-[clamp(1.5rem,2.6vw,2rem)] font-bold leading-none tabular-nums"
              style={{ color: accent ?? C.orange, opacity: 0.35 }}
            >
              {numeral}
            </span>
          )}
          {title}
        </h2>
      </div>
      {action}
    </div>
  );
}
