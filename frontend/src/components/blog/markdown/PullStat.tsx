/* eslint-disable @typescript-eslint/no-explicit-any */
import type { ReactNode } from 'react';
import { C } from '@/lib/brand';

export function PullStat({ node, children }: { node?: any; children?: ReactNode }) {
  const value = (node?.properties?.value as string)?.trim();
  return (
    <div className="my-7 flex flex-col items-center gap-3 rounded-2xl border px-6 py-8 text-center" style={{ background: C.paleBlue, borderColor: C.border }}>
      <p className="text-[clamp(2.6rem,8vw,4rem)] font-bold leading-none tabular-nums" style={{ fontFamily: 'var(--font-serif)', color: C.blue }}>
        {value}
      </p>
      <div
        className="max-w-md text-[14.5px] leading-relaxed [&_a]:font-medium [&_a]:text-[#f17105] [&_a]:underline [&_p:first-child]:mt-0"
        style={{ color: C.ink, opacity: 0.78 }}
      >
        {children}
      </div>
    </div>
  );
}
