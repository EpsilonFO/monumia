/* eslint-disable @typescript-eslint/no-explicit-any */
import { C } from '@/lib/brand';

interface Row {
  aspect: string;
  a: string;
  b: string;
}

function parseRows(node: any): Row[] {
  try {
    return JSON.parse((node?.properties?.data as string) ?? '[]');
  } catch {
    return [];
  }
}

function Tableau({ rows, cola, colb }: { rows: Row[]; cola: string; colb: string }) {
  const cols = 'grid grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)_minmax(0,1fr)]';
  return (
    <div className="my-6 overflow-hidden rounded-2xl border" style={{ background: C.card, borderColor: C.border }}>
      <div className={`${cols} border-b`} style={{ borderColor: C.border }}>
        <div className="px-4 py-2.5" />
        <div className="px-4 py-2.5 text-[13.5px] font-semibold uppercase tracking-[0.08em]" style={{ color: C.blue, background: C.paleBlue }}>
          {cola}
        </div>
        <div className="px-4 py-2.5 text-[13.5px] font-semibold uppercase tracking-[0.08em]" style={{ color: C.orange, background: C.paleOrange }}>
          {colb}
        </div>
      </div>
      {rows.map((r, i) => (
        <div key={i} className={`${cols} border-b last:border-b-0`} style={{ borderColor: C.border }}>
          <div className="px-4 py-3 text-[14.5px] font-semibold" style={{ color: C.ink, opacity: 0.7 }}>
            {r.aspect}
          </div>
          <div className="px-4 py-3 text-[15.5px] leading-snug" style={{ color: C.ink }}>
            {r.a}
          </div>
          <div className="px-4 py-3 text-[15.5px] leading-snug" style={{ color: C.ink }}>
            {r.b}
          </div>
        </div>
      ))}
    </div>
  );
}

function Cartes({ rows, cola, colb }: { rows: Row[]; cola: string; colb: string }) {
  const card = (title: string, accent: string, tint: string, pick: (r: Row) => string) => (
    <div className="flex-1 overflow-hidden rounded-2xl border" style={{ background: C.card, borderColor: C.border }}>
      <div className="px-5 py-3 text-[15px] font-semibold uppercase tracking-[0.08em]" style={{ color: accent, background: tint }}>
        {title}
      </div>
      <dl className="px-5 py-1">
        {rows.map((r, i) => (
          <div key={i} className="border-b py-3 last:border-b-0" style={{ borderColor: C.border }}>
            <dt className="text-[13.5px] font-semibold uppercase tracking-[0.06em]" style={{ color: C.ink, opacity: 0.5 }}>
              {r.aspect}
            </dt>
            <dd className="mt-1 text-[16px] leading-snug" style={{ color: C.ink }}>
              {pick(r)}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
  return (
    <div className="my-6 flex flex-col gap-3 sm:flex-row">
      {card(cola, C.blue, C.paleBlue, (r) => r.a)}
      {card(colb, C.orange, C.paleOrange, (r) => r.b)}
    </div>
  );
}

export function Comparison({ node }: { node?: any }) {
  const rows = parseRows(node);
  if (rows.length === 0) return null;
  const cola = (node?.properties?.cola as string) || 'Option A';
  const colb = (node?.properties?.colb as string) || 'Option B';
  const display = (node?.properties?.display as string) ?? 'tableau';
  if (display === 'cartes') return <Cartes rows={rows} cola={cola} colb={colb} />;
  return <Tableau rows={rows} cola={cola} colb={colb} />;
}
