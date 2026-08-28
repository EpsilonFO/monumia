import { Check } from 'lucide-react';
import {
  IconChantier,
  IconDiagnostic,
  IconListe,
  IconLocalisation,
  IconProjet,
  LogoMonumia,
  type IconComponent,
} from '@/components/icons';
import { Clover } from '@/components/illustrations';
import { C, SERIF } from '@/lib/brand';
import { PROTECTION_LABELS_SHORT } from '@/constants/monument-options';
import type { Monument } from '@/types';

/** Clé d'étape — une chaîne, pas un rang : le wizard projet en insère une de
 *  plus quand le monument n'a jamais répondu à la question du péril. */
export type WizardStepKey = string;

export interface WizardStep {
  key: WizardStepKey;
  label: string;
  hint: string;
  icon: IconComponent;
}

/** Progression du questionnaire : index 0-based, index === total sur l'écran de fin. */
export interface WizardProgress {
  index: number;
  total: number;
}

/** Étape optionnelle en tête du wizard projet : le monument a été créé avant
 *  que la question du péril n'existe, elle n'a donc jamais été posée. Sans ce
 *  rattrapage, elle ne le serait plus jamais. */
export const PERIL_RATTRAPAGE_STEP: WizardStep = {
  key: 'peril',
  label: 'État du monument',
  hint: 'Une question restée sans réponse sur votre fiche.',
  icon: IconDiagnostic,
};

/** Création d'un projet de travaux sur un monument déjà décrit. */
export const PROJET_WIZARD_STEPS: WizardStep[] = [
  {
    key: 'intention',
    label: 'Votre projet',
    hint: 'Ce que vous voulez faire : les aides suivent votre intention.',
    icon: IconProjet,
  },
  {
    key: 'travaux',
    label: 'Les travaux',
    hint: 'Sur quoi porte le chantier — certaines aides ne financent qu’un ouvrage.',
    icon: IconChantier,
  },
  {
    key: 'questionnaire',
    label: 'Questionnaire',
    hint: 'Des questions simples, sans aucun document.',
    icon: IconListe,
  },
  {
    key: 'diagnostic',
    label: 'Diagnostic',
    hint: 'Les aides mobilisables pour votre projet.',
    icon: IconDiagnostic,
  },
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

interface WizardRailProps {
  steps: WizardStep[];
  step: WizardStepKey;
  monument: Monument | null;
  /** Accepté pour stabilité d'interface (header mobile du shell l'utilise). */
  progress: WizardProgress | null;
  onQuit: () => void;
}

/**
 * Rail latéral persistant du wizard (desktop uniquement — le shell affiche un
 * header compact en mobile). Reprend le langage du ParcoursTrail : pastille
 * verte + coche (fait), orange + halo (en cours), cercle clair cerclé (à
 * venir). Aucun état propre : tout vient des props.
 */
export function WizardRail({ steps, step, monument, onQuit }: WizardRailProps) {
  // Les clés étant des chaînes, c'est le RANG dans la liste qui dit ce qui est
  // fait et ce qui reste : une comparaison de clés n'aurait aucun sens.
  const currentIndex = steps.findIndex((s) => s.key === step);
  const tone = monument
    ? (PROTECTION_TONE[monument.protection] ?? PROTECTION_TONE.non_protege)
    : PROTECTION_TONE.non_protege;

  return (
    <aside
      className="hidden w-[320px] shrink-0 flex-col justify-between overflow-y-auto p-6 lg:flex"
      style={{ background: C.card, boxShadow: 'var(--shadow-nav)' }}
    >
      <div className="space-y-8">
        <button
          type="button"
          onClick={onQuit}
          className="flex items-center gap-2.5"
          aria-label="Quitter"
        >
          <LogoMonumia className="h-8 w-8" />
          <span
            className="text-[18px] font-bold tracking-[-0.01em]"
            style={{ fontFamily: SERIF, color: C.ink }}
          >
            Monumia
          </span>
        </button>

        <ol className="space-y-0" aria-label="Étapes">
          {steps.map((s, i) => {
            const state = i < currentIndex ? 'done' : i === currentIndex ? 'current' : 'upcoming';
            const done = state === 'done';
            const current = state === 'current';
            const Icon = s.icon;
            return (
              <li
                key={s.key}
                aria-current={current ? 'step' : undefined}
                aria-label={`${s.label} (${STATE_TEXT[state]})`}
              >
                <div className="flex items-start gap-3 py-1">
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
                  <span aria-hidden className="min-w-0 pt-0.5">
                    <span
                      className="block text-[14px] leading-tight"
                      style={{
                        color: current ? C.ink : done ? C.grayFg : C.grayMuted,
                        fontWeight: current ? 700 : 500,
                      }}
                    >
                      {s.label}
                    </span>
                    <span
                      className="mt-0.5 block text-[12px] leading-snug"
                      style={{ color: C.grayMuted, opacity: done ? 0.75 : 1 }}
                    >
                      {done ? 'Fait !' : s.hint}
                    </span>
                  </span>
                </div>
                {i < steps.length - 1 && (
                  <span
                    aria-hidden
                    className="ml-[17px] block h-4 w-[2px] rounded-full"
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

      <div className="mt-8 flex justify-end pr-1">
        <Clover size={34} className="shrink-0" style={{ color: C.orange, opacity: 0.22 }} />
      </div>
    </aside>
  );
}
