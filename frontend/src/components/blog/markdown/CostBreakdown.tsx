/* eslint-disable @typescript-eslint/no-explicit-any */
import { C } from '@/lib/brand';
import { readData } from './blockData';

interface Line {
  label: string;
  value: number;
}

export function CostBreakdown({ node }: { node?: any }) {
  const lines = readData<Line>(node);
  if (lines.length === 0) return null;
  const unit = (node?.properties?.unit as string) ?? '€';
  const total = lines.reduce((s, l) => s + l.value, 0);
  const fmt = (n: number) => n.toLocaleString('fr-FR');
  return (
    <div className="my-6 overflow-hidden rounded-2xl border" style={{ background: C.card, borderColor: C.border }}>
      {lines.map((l, i) => (
        <div key={i} className="flex items-baseline justify-between gap-4 border-b px-5 py-3" style={{ borderColor: C.border }}>
          <span className="text-[16px]" style={{ color: C.ink, opacity: 0.85 }}>
            {l.label}
          </span>
          <span className="text-[16px] font-semibold tabular-nums" style={{ color: C.ink }}>
            {fmt(l.value)} {unit}
          </span>
        </div>
      ))}
      <div className="flex items-baseline justify-between gap-4 px-5 py-3.5" style={{ background: C.paleOrange }}>
        <span className="text-[14px] font-semibold uppercase tracking-[0.12em]" style={{ color: C.orange }}>
          Total
        </span>
        <span className="text-[23px] font-bold tabular-nums" style={{ fontFamily: 'var(--font-serif)', color: C.orange }}>
          {fmt(total)} {unit}
        </span>
      </div>
    </div>
  );
}
