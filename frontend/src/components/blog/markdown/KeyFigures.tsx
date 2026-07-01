/* eslint-disable @typescript-eslint/no-explicit-any */
import { C } from '@/lib/brand';
import { ProgressRing } from '@/components/dashboard/charts/ProgressRing';
import { readData } from './blockData';

interface Figure {
  value: string;
  label: string;
}

/** Premier nombre trouvé dans une chaîne (gère « 35 % », « ~20 000 € »). */
function numOf(value: string): number | null {
  const m = value.replace(/\s/g, '').match(/-?[\d.,]+/);
  if (!m) return null;
  const n = Number(m[0].replace(',', '.'));
  return Number.isFinite(n) ? n : null;
}

function Cartes({ figures }: { figures: Figure[] }) {
  return (
    <div className="my-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
      {figures.map((f, i) => (
        <div key={i} className="rounded-2xl border px-5 py-4" style={{ background: C.card, borderColor: C.border }}>
          <p className="text-[30px] font-bold leading-none tabular-nums" style={{ fontFamily: 'var(--font-serif)', color: C.orange }}>
            {f.value}
          </p>
          <p className="mt-2 text-[13px] leading-snug" style={{ color: C.ink, opacity: 0.7 }}>
            {f.label}
          </p>
        </div>
      ))}
    </div>
  );
}

function Jauges({ figures }: { figures: Figure[] }) {
  return (
    <div className="my-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {figures.map((f, i) => {
        const n = numOf(f.value);
        return (
          <div
            key={i}
            className="flex flex-col items-center gap-2.5 rounded-2xl border px-4 py-5 text-center"
            style={{ background: C.card, borderColor: C.border }}
          >
            {n === null ? (
              <span className="text-[26px] font-bold tabular-nums" style={{ fontFamily: 'var(--font-serif)', color: C.orange }}>
                {f.value}
              </span>
            ) : (
              <ProgressRing value={n} size={84} color={C.orange} label={f.label} />
            )}
            <p className="text-[13px] leading-snug" style={{ color: C.ink, opacity: 0.7 }}>
              {f.label}
            </p>
          </div>
        );
      })}
    </div>
  );
}

export function KeyFigures({ node }: { node?: any }) {
  const figures = readData<Figure>(node);
  if (figures.length === 0) return null;
  const display = (node?.properties?.display as string) ?? 'cartes';
  if (display === 'jauge') return <Jauges figures={figures} />;
  return <Cartes figures={figures} />;
}
