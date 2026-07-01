import type { ReactNode } from 'react';
import { C } from '@/lib/brand';

/** En-tête de section éditorial du blog : filet orange + eyebrow + titre serif. */
export function BlogSectionHeading({
  eyebrow,
  title,
  action,
}: {
  eyebrow: string;
  title: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-4 flex items-end justify-between gap-4">
      <div>
        <span
          className="inline-flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em]"
          style={{ color: C.blue }}
        >
          <span aria-hidden style={{ width: 18, height: 2, borderRadius: 2, background: C.orange }} />
          {eyebrow}
        </span>
        <h2
          className="mt-1.5 text-[clamp(1.15rem,2vw,1.5rem)] leading-tight"
          style={{ fontFamily: 'var(--font-serif)', color: C.ink }}
        >
          {title}
        </h2>
      </div>
      {action}
    </div>
  );
}
