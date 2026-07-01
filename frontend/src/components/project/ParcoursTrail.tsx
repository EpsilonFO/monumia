import { Check } from 'lucide-react';
import {
  IconDiagnostic,
  IconDossier,
  IconDepot,
  IconSuivi,
  type IconComponent,
} from '@/components/icons';
import { C } from '@/lib/brand';
import { PROJECT_STAGES } from '@/lib/project-stats';
import { jalonState } from '@/lib/project-card-view';
import type { ProjectStage, ProjectStageKey } from '@/lib/project-stats';

/** Une icône « imagée » par étape du parcours. */
const STAGE_ICON: Record<ProjectStageKey, IconComponent> = {
  estimation: IconDiagnostic,
  dossier: IconDossier,
  depot: IconDepot,
  suivi: IconSuivi,
};

/**
 * « Chemin » horizontal illustré : 4 jalons reliés, franchis en orange (coche),
 * étape en cours mise en valeur (anneau), étapes à venir en bleu pâle.
 */
export function ParcoursTrail({ stage }: { stage: ProjectStage }) {
  const currentLabel =
    stage.reachedIndex >= 0 ? PROJECT_STAGES[stage.reachedIndex].label : null;
  const last = PROJECT_STAGES.length - 1;

  return (
    <div className="space-y-2.5">
      <ol className="flex items-start" aria-label="Avancement du projet">
        {PROJECT_STAGES.map((s, i) => {
          const state = jalonState(i, stage.reachedIndex);
          const done = state === 'done';
          const current = state === 'current';
          const active = done || current;
          const Icon = STAGE_ICON[s.key];
          return (
            <li key={s.key} className="flex flex-1 flex-col items-center gap-1.5">
              <div className="flex w-full items-center">
                <span
                  className="h-0.5 flex-1 rounded-full"
                  style={{ background: i === 0 ? 'transparent' : active ? C.orange : C.border }}
                />
                <span
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-colors"
                  style={{
                    background: active ? C.orange : C.paleBlue,
                    color: active ? '#fff' : C.blue,
                    boxShadow: current ? `0 0 0 4px ${C.paleOrange}` : 'none',
                  }}
                >
                  {done ? (
                    <Check className="h-4 w-4" strokeWidth={3} aria-hidden />
                  ) : (
                    <Icon className="h-4 w-4" strokeWidth={2} aria-hidden />
                  )}
                </span>
                <span
                  className="h-0.5 flex-1 rounded-full"
                  style={{ background: i === last ? 'transparent' : done ? C.orange : C.border }}
                />
              </div>
              <span
                className="text-center text-[11px] font-medium leading-tight"
                style={{ color: active ? C.ink : C.grayMuted }}
              >
                {s.label}
              </span>
            </li>
          );
        })}
      </ol>
      <p className="text-center text-[12px]" style={{ color: C.grayMuted }}>
        {currentLabel ? (
          <>
            Vous en êtes à :{' '}
            <span className="font-semibold" style={{ color: C.ink }}>
              {currentLabel}
            </span>
          </>
        ) : (
          'Parcours pas encore commencé'
        )}
      </p>
    </div>
  );
}
