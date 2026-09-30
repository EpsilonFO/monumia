import { C } from '@/lib/brand';
import { extractHeadings } from './extractHeadings';
import { useActiveHeading } from './useActiveHeading';

export function Toc({ body }: { body: string }) {
  const headings = extractHeadings(body);
  const ids = headings.map((h) => h.id);
  const active = useActiveHeading(ids);
  if (headings.length < 2) return null;
  const activeIdx = Math.max(0, headings.findIndex((h) => h.id === active));

  return (
    <nav aria-label="Sommaire" className="text-[15px]">
      <p className="mb-3 text-[13px] font-semibold uppercase tracking-[0.18em]" style={{ color: C.blue, opacity: 0.55 }}>
        Sommaire
      </p>
      <ol className="flex flex-col">
        {headings.map((h, i) => {
          const done = i <= activeIdx;
          const isActive = i === activeIdx;
          const last = i === headings.length - 1;
          return (
            <li key={h.id} className="relative flex gap-3">
              <div className="relative flex w-3 shrink-0 justify-center">
                {!last && (
                  <span
                    className="absolute top-3 w-0.5"
                    style={{ height: 'calc(100% - 0.25rem)', background: i < activeIdx ? C.orange : C.border }}
                    aria-hidden
                  />
                )}
                <span
                  className="z-10 mt-1.5 block h-2.5 w-2.5 rounded-full transition-colors duration-300"
                  style={{
                    background: done ? C.orange : C.card,
                    border: `2px solid ${done ? C.orange : C.border}`,
                    boxShadow: `0 0 0 3px ${C.cream}`,
                  }}
                  aria-hidden
                />
              </div>
              <a
                href={`#${h.id}`}
                className="block py-1 leading-snug transition-colors duration-200"
                style={{ color: C.ink, opacity: isActive ? 1 : 0.5, fontWeight: isActive ? 600 : 400 }}
                aria-current={isActive ? 'true' : undefined}
              >
                {h.text}
              </a>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
