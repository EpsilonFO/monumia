import { Check } from 'lucide-react';
import {
  IconAide,
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

export const WIZARD_STEPS: Array<{
  key: WizardStepKey;
  label: string;
  hint: string;
  icon: IconComponent;
}> = [
  {
    key: 1,
    label: 'Votre monument',
    hint: 'Retrouvez-le dans la base Mérimée ou décrivez-le vous-même.',
    icon: IconMonument,
  },
  {
    key: 2,
    label: 'Questionnaire',
    hint: 'Des questions simples, sans aucun document.',
    icon: IconListe,
  },
  {
    key: 3,
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

/**
 * Message chaleureux du rail, fonction de la progression. Volontairement
 * sobre (pas de gamification lourde) : il rassure, il ne distrait pas.
 * Chaîne vide = rien à dire (début de parcours) : l'appelant masque la zone.
 */
export function encouragement(step: WizardStepKey, progress: WizardProgress | null): string {
  if (step === 1) return '';
  if (step === 3) return 'Votre diagnostic arrive…';
  if (!progress || progress.total === 0) return '';
  if (progress.index >= progress.total) return 'C’est tout !';
  const remaining = progress.total - progress.index;
  const ratio = progress.index / progress.total;
  if (ratio >= 0.75) return 'Presque fini !';
  if (ratio >= 0.5) {
    return remaining === 1 ? 'Plus qu’une question !' : `Plus que ${remaining} questions\u00a0!`;
  }
  return '';
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
      className="hidden w-[320px] shrink-0 flex-col justify-between overflow-y-auto p-6 lg:flex"
      style={{ background: C.card, boxShadow: 'var(--shadow-nav)' }}
    >
      <div className="space-y-8">
        <button
          type="button"
          onClick={onQuit}
          className="flex items-center gap-2.5"
          aria-label="Quitter la création de projet"
        >
          <img src="/monumia.png" alt="" className="h-8 w-8" aria-hidden />
          <span
            className="text-[18px] font-bold tracking-[-0.01em]"
            style={{ fontFamily: SERIF, color: C.ink }}
          >
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
                {i < WIZARD_STEPS.length - 1 && (
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

        {monument ? (
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
        ) : (
          // La place du monument est réservée dès le départ : l'utilisateur
          // voit où son choix va s'inscrire.
          <div
            className="flex items-center gap-3 rounded-2xl border border-dashed p-4"
            style={{ borderColor: `color-mix(in srgb, ${C.blue} 25%, transparent)` }}
          >
            <span
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
              style={{ background: 'var(--secondary)', color: C.blue }}
            >
              <IconMonument className="h-5 w-5" />
            </span>
            <p className="text-[13px] leading-snug" style={{ color: C.grayMuted }}>
              Votre monument apparaîtra ici dès que vous l&rsquo;aurez choisi.
            </p>
          </div>
        )}
      </div>

      <div className="mt-8 space-y-3">
        {/* Ce que le parcours rapporte, toujours visible : on avance pour
            quelque chose de concret. */}
        <div
          className="flex items-start gap-3 rounded-2xl p-4"
          style={{ background: 'var(--warning-muted)' }}
        >
          <span
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
            style={{ background: C.orange, color: '#fff' }}
          >
            <IconAide className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.14em]"
              style={{ color: C.orange }}
            >
              À la clé
            </p>
            <p className="mt-1 text-[13px] leading-snug" style={{ color: C.ink }}>
              La liste des aides publiques mobilisables pour votre projet, prête à consulter.
            </p>
          </div>
        </div>

        {encouragement(step, progress) ? (
          // Encart signature : bleu profond institutionnel, écriture manuscrite
          // crème, quadrilobe orange vif — le duo Monumia condensé.
          <div
            className="relative flex items-center justify-between gap-3 overflow-hidden rounded-2xl p-4"
            style={{ background: C.blue }}
          >
            <Clover
              size={72}
              className="pointer-events-none absolute -bottom-5 -right-4"
              style={{ color: '#fff', opacity: 0.08 }}
            />
            <p
              aria-live="polite"
              className="relative text-[22px] leading-tight"
              style={{ fontFamily: "'Caveat', cursive", color: 'var(--primary-foreground)' }}
            >
              {encouragement(step, progress)}
            </p>
            <Clover size={34} className="relative shrink-0" style={{ color: C.orangeVif }} />
          </div>
        ) : (
          <div className="flex justify-end pr-1">
            <Clover size={34} className="shrink-0" style={{ color: C.orange, opacity: 0.22 }} />
          </div>
        )}
      </div>
    </aside>
  );
}
