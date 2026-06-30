/* eslint-disable @typescript-eslint/no-explicit-any */
import type { ReactNode } from 'react';
import { Scale } from 'lucide-react';
import { C } from '@/lib/brand';

export function Quote({ node, children }: { node?: any; children?: ReactNode }) {
  const source = (node?.properties?.source as string)?.trim();
  return (
    <figure className="my-6 overflow-hidden rounded-2xl border p-5 pl-6" style={{ background: C.paleBlue, borderColor: C.border }}>
      <div className="flex gap-3.5">
        <Scale className="mt-1 h-5 w-5 shrink-0" style={{ color: C.blue }} aria-hidden />
        <div className="min-w-0">
          <blockquote
            className="text-[15px] italic leading-relaxed [&_p]:mt-2 [&_p:first-child]:mt-0"
            style={{ color: C.ink, fontFamily: 'var(--font-serif)' }}
          >
            {children}
          </blockquote>
          {source && (
            <figcaption className="mt-3 text-[12px] font-semibold uppercase tracking-[0.12em]" style={{ color: C.blue, opacity: 0.7 }}>
              {source}
            </figcaption>
          )}
        </div>
      </div>
    </figure>
  );
}
