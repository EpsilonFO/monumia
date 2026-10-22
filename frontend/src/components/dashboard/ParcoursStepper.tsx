import { Check } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { C } from '@/lib/brand';
import { PROJECT_STAGES } from '@/lib/project-stats';
import type { ProjectStage } from '@/lib/project-stats';

export function ParcoursStepper({ stage }: { stage: ProjectStage }) {
  const { t } = useTranslation('dashboard');
  return (
    <ol className="flex items-center gap-1.5" aria-label={t('ParcoursStepper.avancement')}>
      {PROJECT_STAGES.map((s, i) => {
        const reached = i <= stage.reachedIndex;
        const isCurrent = i === stage.reachedIndex;
        return (
          <li key={s.key} className="flex flex-1 items-center gap-1.5">
            <span className="flex items-center gap-1.5">
              <span
                className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[12px] font-bold"
                style={{
                  background: reached ? C.orange : C.paleBlue,
                  color: reached ? '#fff' : C.blue,
                  boxShadow: isCurrent ? `0 0 0 3px ${C.paleOrange}` : 'none',
                }}
              >
                {reached ? <Check className="h-3 w-3" strokeWidth={3} aria-hidden /> : i + 1}
              </span>
              <span
                className="hidden whitespace-nowrap text-[13px] font-medium md:inline"
                style={{ color: reached ? C.ink : C.grayMuted }}
              >
                {s.label}
              </span>
            </span>
            {i < PROJECT_STAGES.length - 1 && (
              <span className="h-0.5 flex-1 rounded-full" style={{ background: i < stage.reachedIndex ? C.orange : C.border }} />
            )}
          </li>
        );
      })}
    </ol>
  );
}
