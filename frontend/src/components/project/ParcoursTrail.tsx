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
 * Frise de progression dépouillée : 4 jalons reliés, teintés à la couleur du
 * projet (`accent`). Franchi = pastille pleine + coche ; en cours = pastille
 * pleine + halo coloré ; à venir = pastille claire cerclée. Aucun libellé sous
 * les jalons — l'étape en cours est nommée en clair par la carte (une ligne).
 */
export function ParcoursTrail({ stage, accent }: { stage: ProjectStage; accent: string }) {
  const last = PROJECT_STAGES.length - 1;

  return (
    <ol className="flex items-center" aria-label="Avancement du projet">
      {PROJECT_STAGES.map((s, i) => {
        const state = jalonState(i, stage.reachedIndex);
        const done = state === 'done';
        const current = state === 'current';
        const active = done || current;
        const Icon = STAGE_ICON[s.key];
        return (
          <li key={s.key} className="flex flex-1 items-center last:flex-none">
            <span
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full transition-colors"
              style={{
                background: active ? accent : C.card,
                color: active ? '#fff' : C.grayMuted,
                border: active ? 'none' : `2px solid ${C.border}`,
                boxShadow: current ? `0 0 0 4px color-mix(in srgb, ${accent} 24%, transparent)` : 'none',
              }}
            >
              {done ? (
                <Check className="h-5 w-5" strokeWidth={3} aria-hidden />
              ) : (
                <Icon className="h-5 w-5" strokeWidth={2} aria-hidden />
              )}
            </span>
            {i < last && (
              <span
                className="mx-1.5 h-1 flex-1 rounded-full"
                style={{ background: done ? accent : C.border }}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
