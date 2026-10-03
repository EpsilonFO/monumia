/* eslint-disable @typescript-eslint/no-explicit-any */
import { C } from '@/lib/brand';
import { readData } from './blockData';

interface Event {
  date: string;
  event: string;
}

export function Timeline({ node }: { node?: any }) {
  const items = readData<Event>(node);
  if (items.length === 0) return null;
  return (
    <ol className="my-6 flex flex-col" aria-label="Chronologie">
      {items.map((it, i) => {
        const last = i === items.length - 1;
        return (
          <li key={i} className="relative flex gap-4 pb-5 last:pb-0">
            {!last && (
              <span
                className="frise-draw absolute left-[6px] top-[20.5px] bottom-0 w-0.5"
                style={{ background: C.blueLight, animationDelay: `${i * 80 + 40}ms` }}
                aria-hidden
              />
            )}
            <span
              className="frise-pop relative z-10 mt-[7px] h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ background: C.blue, boxShadow: `0 0 0 3px ${C.card}`, animationDelay: `${i * 80}ms` }}
              aria-hidden
            />
            <div className="min-w-0">
              <p className="text-[16px] font-bold leading-none tabular-nums" style={{ fontFamily: 'var(--font-serif)', color: C.blue }}>
                {it.date}
              </p>
              <p className="mt-1.5 text-[16.5px] leading-relaxed" style={{ color: C.ink, opacity: 0.82 }}>
                {it.event}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
