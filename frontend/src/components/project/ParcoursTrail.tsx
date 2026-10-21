import { Check } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import {
  IconDiagnostic,
  IconDossier,
  IconDepot,
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
};

/**
 * Frise de progression à étapes NOMMÉES : chaque jalon porte son libellé en
 * toutes lettres (public peu à l'aise avec l'informatique — pas de code
 * visuel implicite). Fait = pastille verte + coche ; en cours = pastille
 * orange + halo + libellé en gras ; à venir = pastille claire cerclée.
 * Horizontale sur desktop, elle devient une liste verticale (façon
 * check-list) sur mobile où les libellés ne tiennent plus côte à côte.
 *
 * L'état est annoncé via `aria-label` sur chaque jalon — PAS de span
 * `sr-only` : positionnés en absolu hors de tout ancêtre positionné, ils
 * débordaient du viewport et créaient une scrollbar fantôme sur <html>.
 */
export function ParcoursTrail({ stage }: { stage: ProjectStage }) {
  const { t } = useTranslation('project');
  const last = PROJECT_STAGES.length - 1;

  return (
    <ol
      className="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:gap-0"
      aria-label={t('ParcoursTrail.avancement')}
    >
      {PROJECT_STAGES.map((s, i) => {
        const state = jalonState(i, stage.reachedIndex);
        const done = state === 'done';
        const current = state === 'current';
        const Icon = STAGE_ICON[s.key];
        return (
          <li
            key={s.key}
            className="flex items-center sm:flex-1 sm:last:flex-none"
            aria-current={current ? 'step' : undefined}
            aria-label={t('ParcoursTrail.jalon', { etape: s.label, etat: t(`etatsEtape.${state}`) })}
          >
            <span
              aria-hidden
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-colors"
              style={{
                background: done ? C.success : current ? C.orange : C.card,
                color: done || current ? '#fff' : C.grayMuted,
                // Neutres bleutés : la frise vit sur la tuile bleu pâle de la carte.
                border:
                  done || current
                    ? 'none'
                    : `2px solid color-mix(in srgb, ${C.blue} 22%, transparent)`,
                boxShadow: current
                  ? `0 0 0 5px color-mix(in srgb, ${C.orange} 22%, transparent)`
                  : 'none',
              }}
            >
              {done ? (
                <Check className="h-4 w-4" strokeWidth={3} />
              ) : (
                <Icon className="h-4 w-4" weight="bold" />
              )}
            </span>
            <span
              aria-hidden
              className="ml-2 whitespace-nowrap text-[15px]"
              style={{
                color: current ? C.ink : done ? C.grayFg : C.grayMuted,
                fontWeight: current ? 700 : 500,
              }}
            >
              {s.label}
            </span>
            {i < last && (
              <span
                aria-hidden
                className="mx-2.5 hidden h-[2px] min-w-3 flex-1 rounded-full sm:block"
                style={{
                  background: done
                    ? C.success
                    : `color-mix(in srgb, ${C.blue} 16%, transparent)`,
                }}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
