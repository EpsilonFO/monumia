/* eslint-disable @typescript-eslint/no-explicit-any */
import { Check } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { C } from '@/lib/brand';
import { readData } from './blockData';

interface Step {
  title: string;
  description: string;
}

function Frise({ steps }: { steps: Step[] }) {
  const { t } = useTranslation('blog');
  return (
    <ol className="my-6 flex flex-col" aria-label={t('Steps.aria')}>
      {steps.map((s, i) => {
        const last = i === steps.length - 1;
        return (
          <li key={i} className="relative flex gap-3.5 pb-5 last:pb-0">
            {!last && (
              <span
                className="frise-draw absolute left-[15px] top-[16px] bottom-0 w-0.5"
                style={{ background: C.orange, animationDelay: `${i * 80 + 40}ms` }}
                aria-hidden
              />
            )}
            <div className="relative z-10 flex w-7 shrink-0 justify-center">
              <span
                className="frise-pop flex h-7 w-7 items-center justify-center rounded-full text-[15px] font-bold text-white"
                style={{ background: C.orange, fontFamily: 'var(--font-serif)', boxShadow: `0 0 0 3px ${C.card}`, animationDelay: `${i * 80}ms` }}
              >
                {i + 1}
              </span>
            </div>
            <div className="pt-0.5 text-[16.5px] leading-relaxed">
              {s.title && (
                <span className="font-semibold" style={{ color: C.ink }}>
                  {s.title}
                </span>
              )}
              {s.title && s.description && <span style={{ color: C.ink, opacity: 0.5 }}>{t('Steps.separateur')}</span>}
              {s.description && <span style={{ color: C.ink, opacity: 0.8 }}>{s.description}</span>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function Colonnes({ steps }: { steps: Step[] }) {
  return (
    <div className="my-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {steps.map((s, i) => (
        <div key={i} className="rounded-2xl border p-4" style={{ background: C.card, borderColor: C.border }}>
          <span
            className="text-[15px] font-bold tabular-nums"
            style={{ fontFamily: 'var(--font-serif)', color: C.orange }}
          >
            {String(i + 1).padStart(2, '0')}
          </span>
          {s.title && (
            <p className="mt-1.5 text-[16.5px] font-semibold leading-snug" style={{ color: C.ink }}>
              {s.title}
            </p>
          )}
          {s.description && (
            <p className="mt-1 text-[15px] leading-snug" style={{ color: C.ink, opacity: 0.7 }}>
              {s.description}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

function ChecklistView({ steps }: { steps: Step[] }) {
  const { t } = useTranslation('blog');
  return (
    <ul className="my-6 flex flex-col gap-2.5 rounded-2xl border p-5" style={{ background: C.card, borderColor: C.border }}>
      {steps.map((s, i) => (
        <li key={i} className="flex items-start gap-3 text-[16.5px] leading-snug">
          <span
            className="mt-[2px] flex h-[20.5px] w-[20.5px] shrink-0 items-center justify-center rounded-full"
            style={{ background: C.paleOrange }}
            aria-hidden
          >
            <Check className="h-3 w-3" style={{ color: C.orange }} />
          </span>
          <span>
            {s.title && (
              <span className="font-semibold" style={{ color: C.ink }}>
                {s.title}
              </span>
            )}
            {s.title && s.description && <span style={{ color: C.ink, opacity: 0.5 }}>{t('Steps.separateur')}</span>}
            {s.description && <span style={{ color: C.ink, opacity: 0.8 }}>{s.description}</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function Steps({ node }: { node?: any }) {
  const steps = readData<Step>(node);
  if (steps.length === 0) return null;
  const display = (node?.properties?.display as string) ?? 'frise';
  if (display === 'colonnes') return <Colonnes steps={steps} />;
  if (display === 'checklist') return <ChecklistView steps={steps} />;
  return <Frise steps={steps} />;
}
