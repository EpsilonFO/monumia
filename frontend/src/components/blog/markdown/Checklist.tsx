/* eslint-disable @typescript-eslint/no-explicit-any */
import { C } from '@/lib/brand';
import { readData } from './blockData';

export function Checklist({ node }: { node?: any }) {
  const items = readData<string>(node);
  if (items.length === 0) return null;
  const title = (node?.properties?.title as string)?.trim();
  return (
    <div className="my-6 rounded-2xl border p-5" style={{ background: C.card, borderColor: C.border }}>
      {title && (
        <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: C.orange }}>
          {title}
        </p>
      )}
      <ul className="flex flex-col gap-2.5">
        {items.map((it, i) => (
          <li key={i} className="flex items-start gap-3 text-[14.5px] leading-snug" style={{ color: C.ink }}>
            <span
              className="mt-[2px] flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-[5px] border-2"
              style={{ borderColor: C.orange }}
              aria-hidden
            >
              <span className="h-2 w-2 rounded-[1px]" style={{ background: C.paleOrange }} />
            </span>
            <span>{it}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
