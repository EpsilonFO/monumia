import { Check } from 'lucide-react';
import {
  IconDiagnostic,
  IconListe,
  IconLocalisation,
  IconMonument,
  type IconComponent,
} from '@/components/icons';
import { Clover } from '@/components/illustrations';
import { C, SERIF } from '@/lib/brand';
import { PROTECTION_LABELS_SHORT } from '@/constants/monument-options';
import type { Monument } from '@/types';

export type WizardStepKey = 1 | 2 | 3;

/** Progression du questionnaire : index 0-based, index === total sur l'écran de fin. */
export interface WizardProgress {
  index: number;
  total: number;
}

export const WIZARD_STEPS: Array<{ key: WizardStepKey; label: string; icon: IconComponent }> = [
  { key: 1, label: 'Votre monument', icon: IconMonument },
  { key: 2, label: 'Questionnaire', icon: IconListe },
  { key: 3, label: 'Diagnostic', icon: IconDiagnostic },
];

// Mêmes tonalités que MonumentFiche (bg pâle + texte soutenu par niveau).
const PROTECTION_TONE: Record<string, { bg: string; fg: string }> = {
  classe: { bg: 'var(--secondary)', fg: 'var(--primary)' },
  inscrit: { bg: 'var(--info-muted)', fg: 'var(--info)' },
  abords: { bg: 'var(--cat-3-soft)', fg: 'var(--cat-3)' },
  spr: { bg: 'var(--cat-4-soft)', fg: 'var(--cat-4)' },
  non_protege: { bg: 'var(--muted)', fg: 'var(--gray-fg)' },
};

const STATE_TEXT = { done: 'étape faite', current: 'étape en cours', upcoming: 'étape à venir' };

/**
 * Message chaleureux du rail, fonction de la progression. Volontairement
 * sobre (pas de gamification lourde) : il rassure, il ne distrait pas.
 */
export function encouragement(step: WizardStepKey, progress: WizardProgress | null): string {
  if (step === 1) return 'C’est parti !';
  if (step === 3) return 'Votre diagnostic arrive…';
  if (!progress || progress.total === 0) return 'Encore un instant…';
  const remaining = progress.total - progress.index;
  const ratio = progress.index / progress.total;
  if (ratio >= 0.75) return 'Presque fini !';
  if (ratio >= 0.5) {
    return remaining === 1 ? 'Plus qu’une question !' : `Plus que ${remaining} questions !`;
  }
  if (ratio >= 0.25) return 'Vous êtes sur la bonne voie.';
  return 'C’est parti !';
}

interface WizardRailProps {
  step: WizardStepKey;
  monument: Monument | null;
  progress: WizardProgress | null;
  onQuit: () => void;
}

/**
 * Rail latéral persistant du wizard (desktop uniquement — le shell affiche un
 * header compact en mobile). Reprend le langage du ParcoursTrail : pastille
 * verte + coche (fait), orange + halo (en cours), cercle clair cerclé (à
 * venir). Aucun état propre : tout vient des props.
 */
export function WizardRail({ step, monument, progress, onQuit }: WizardRailProps) {
  const tone = monument
    ? (PROTECTION_TONE[monument.protection] ?? PROTECTION_TONE.non_protege)
    : PROTECTION_TONE.non_protege;

  return (
    <aside
      className="hidden w-[320px] shrink-0 flex-col justify-between p-6 lg:flex"
      style={{ background: C.card, boxShadow: 'var(--shadow-nav)' }}
    >
      <div className="space-y-8">
        <button
          type="button"
          onClick={onQuit}
          className="flex items-center gap-2.5"
          aria-label="Quitter la création de projet"
        >
          <Clover size={26} style={{ color: C.blue }} />
          <span className="text-[19px]" style={{ fontFamily: SERIF, color: C.ink }}>
            Monumia
          </span>
        </button>

        <ol className="space-y-0" aria-label="Étapes de la création">
          {WIZARD_STEPS.map((s, i) => {
            const state = s.key < step ? 'done' : s.key === step ? 'current' : 'upcoming';
            const done = state === 'done';
            const current = state === 'current';
            const Icon = s.icon;
            return (
              <li
                key={s.key}
                aria-current={current ? 'step' : undefined}
                aria-label={`${s.label} (${STATE_TEXT[state]})`}
              >
                <div className="flex items-center gap-3 py-1">
                  <span
                    aria-hidden
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-colors"
                    style={{
                      background: done ? C.success : current ? C.orange : C.card,
                      color: done || current ? '#fff' : C.grayMuted,
                      border:
                        done || current
                          ? 'none'
                          : `2px solid color-mix(in srgb, ${C.blue} 22%, transparent)`,
                      boxShadow: current
                        ? `0 0 0 4px color-mix(in srgb, ${C.orange} 22%, transparent)`
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
                    className="text-[14px]"
                    style={{
                      color: current ? C.ink : done ? C.grayFg : C.grayMuted,
                      fontWeight: current ? 700 : 500,
                    }}
                  >
                    {s.label}
                  </span>
                </div>
                {i < WIZARD_STEPS.length - 1 && (
                  <span
                    aria-hidden
                    className="ml-[17px] block h-5 w-[2px] rounded-full"
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

        {monument && (
          <div
            className="rounded-2xl border p-4"
            style={{
              borderColor: C.border,
              background: 'linear-gradient(135deg, var(--secondary) 0%, var(--card) 60%)',
            }}
          >
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.14em]"
              style={{ color: C.grayMuted }}
            >
              Votre monument
            </p>
            <p
              className="mt-1.5 text-[16px] leading-snug"
              style={{ fontFamily: SERIF, color: C.ink }}
            >
              {monument.nom}
            </p>
            {monument.commune && (
              <p className="mt-1 flex items-center gap-1.5 text-[13px]" style={{ color: C.grayFg }}>
                <IconLocalisation className="h-3.5 w-3.5 shrink-0" />
                {monument.commune}
              </p>
            )}
            <span
              className="mt-2.5 inline-flex rounded-full px-2.5 py-1 text-[12px] font-semibold"
              style={{ background: tone.bg, color: tone.fg }}
            >
              {PROTECTION_LABELS_SHORT[monument.protection] ?? monument.protection}
            </span>
          </div>
        )}
      </div>

      <div className="flex items-end justify-between gap-3 pt-8">
        <p
          aria-live="polite"
          className="text-[22px] leading-tight"
          style={{ fontFamily: "'Caveat', cursive", color: C.blue }}
        >
          {encouragement(step, progress)}
        </p>
        <Clover size={40} className="shrink-0" style={{ color: C.orange, opacity: 0.22 }} />
      </div>
    </aside>
  );
}
