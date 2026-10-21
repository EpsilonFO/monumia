/* eslint-disable @typescript-eslint/no-explicit-any */
import { Check, X } from 'lucide-react';
import { Trans, useTranslation } from 'react-i18next';

import { C } from '@/lib/brand';
import { readData } from './blockData';

interface Branch {
  q: string;
  yes: string;
  no: string;
}

export function DecisionTree({ node }: { node?: any }) {
  const { t } = useTranslation('blog');
  const branches = readData<Branch>(node);
  if (branches.length === 0) return null;
  const title = (node?.properties?.title as string)?.trim();
  return (
    <div className="my-6 rounded-2xl border p-5" style={{ background: C.card, borderColor: C.border }}>
      {title && (
        <p className="mb-4 text-[13px] font-semibold uppercase tracking-[0.18em]" style={{ color: C.blue }}>
          {title}
        </p>
      )}
      <div className="flex flex-col gap-4">
        {branches.map((b, i) => (
          <div key={i}>
            <p className="text-[16.5px] font-semibold" style={{ color: C.ink }}>
              {b.q}
            </p>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {b.yes && (
                <div className="flex items-start gap-2 rounded-xl px-3.5 py-2.5" style={{ background: C.paleBlue }}>
                  <Check className="mt-0.5 h-4 w-4 shrink-0" style={{ color: C.blue }} aria-hidden />
                  <span className="text-[15.5px] leading-snug" style={{ color: C.ink }}>
                    <Trans
                      t={t}
                      i18nKey="DecisionTree.oui"
                      values={{ suite: b.yes }}
                      components={{ fort: <strong style={{ color: C.blue }} /> }}
                    />
                  </span>
                </div>
              )}
              {b.no && (
                <div className="flex items-start gap-2 rounded-xl px-3.5 py-2.5" style={{ background: C.paleOrange }}>
                  <X className="mt-0.5 h-4 w-4 shrink-0" style={{ color: C.orange }} aria-hidden />
                  <span className="text-[15.5px] leading-snug" style={{ color: C.ink }}>
                    <Trans
                      t={t}
                      i18nKey="DecisionTree.non"
                      values={{ suite: b.no }}
                      components={{ fort: <strong style={{ color: C.orange }} /> }}
                    />
                  </span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
