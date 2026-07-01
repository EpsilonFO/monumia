/* eslint-disable @typescript-eslint/no-explicit-any */
import { C } from '@/lib/brand';
import { readData } from './blockData';

interface Bar {
  label: string;
  value: number;
}

export function BarChart({ node }: { node?: any }) {
  const bars = readData<Bar>(node);
  if (bars.length === 0) return null;
  const unit = (node?.properties?.unit as string) ?? '%';
  const denom = unit === '%' ? 100 : Math.max(...bars.map((b) => b.value), 1);
  return (
    <div className="my-6 space-y-3.5 rounded-2xl border px-5 py-5" style={{ background: C.card, borderColor: C.border }}>
      {bars.map((b, i) => {
        const pct = Math.max(0, Math.min(100, (b.value / denom) * 100));
        return (
          <div key={i}>
            <div className="flex items-baseline justify-between text-[13px]">
              <span style={{ color: C.ink }}>{b.label}</span>
              <span className="font-bold tabular-nums" style={{ fontFamily: 'var(--font-serif)', color: C.orange }}>
                {b.value}
                {unit ? ` ${unit}` : ''}
              </span>
            </div>
            <div className="mt-1.5 h-2.5 overflow-hidden rounded-full" style={{ background: C.paleOrange }}>
              <div className="h-full rounded-full" style={{ width: `${pct}%`, background: `linear-gradient(90deg, ${C.orange}, ${C.orangeVif})` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
