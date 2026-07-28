import { Check } from 'lucide-react';
import { ArrowRight } from 'lucide-react';
import { RAISON_OPTIONS, type Raison } from '@/constants/raisons';
import { C, SERIF } from '@/lib/brand';
import { cn } from '@/lib/utils';

interface ProjectIntentStepProps {
  value: string[];
  onChange: (raisons: string[]) => void;
  onNext: () => void;
  /** Vrai quand on revient sur l'étape depuis « Refaire le questionnaire ». */
  retake?: boolean;
}

/**
 * Étape « Votre projet » : ce que le propriétaire veut faire, coché sur les
 * quatre finalités du catalogue (`aides_v3.raison`). C'est le seul filtre en
 * amont du questionnaire — sans lui, les faits manquants de TOUTES les aides
 * candidates deviennent des questions, y compris celles d'aides sans rapport
 * avec le projet. Multi-sélection : un chantier peut viser plusieurs finalités.
 */
export function ProjectIntentStep({ value, onChange, onNext, retake }: ProjectIntentStepProps) {
  const toggle = (raison: Raison) => {
    onChange(value.includes(raison) ? value.filter((r) => r !== raison) : [...value, raison]);
  };

  return (
    <div className="space-y-5">
      <div className="space-y-1.5">
        <div
          className="text-[12px] font-semibold uppercase tracking-[0.2em]"
          style={{ color: C.orange }}
        >
          {retake ? 'Questionnaire' : 'Nouveau projet'}
        </div>
        <h1
          className="text-[clamp(1.4rem,3vw,1.8rem)] leading-tight"
          style={{ fontFamily: SERIF, color: C.ink }}
        >
          Que voulez-vous faire&nbsp;?
        </h1>
        <p className="max-w-lg text-[14px] leading-relaxed" style={{ color: C.grayFg }}>
          Plusieurs réponses possibles. Nous ne vous poserons ensuite que les questions
          utiles à votre projet.
        </p>
      </div>

      <div
        role="group"
        aria-label="Finalités de votre projet"
        className="grid grid-cols-1 gap-2.5 sm:grid-cols-2"
      >
        {RAISON_OPTIONS.map((option) => {
          const selected = value.includes(option.value);
          return (
            <button
              key={option.value}
              type="button"
              role="checkbox"
              aria-checked={selected}
              onClick={() => toggle(option.value)}
              className={cn(
                'group flex min-h-[4.5rem] w-full items-start gap-3.5 rounded-2xl border-2 px-4 py-3.5 text-left transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                selected
                  ? 'border-accent bg-warning-muted shadow-[var(--shadow-card)]'
                  : 'border-border bg-card hover:-translate-y-0.5 hover:border-warning hover:shadow-[var(--shadow-pop)]',
              )}
            >
              <span
                aria-hidden
                className={cn(
                  'mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border-2 transition-colors',
                  selected ? 'border-accent bg-accent text-white' : 'border-border',
                )}
              >
                {selected && <Check className="h-3.5 w-3.5" strokeWidth={3} />}
              </span>
              <span className="min-w-0">
                <span
                  className="block text-[15px] font-semibold leading-snug"
                  style={{ color: C.ink }}
                >
                  {option.label}
                </span>
                <span
                  className="mt-0.5 block text-[13px] leading-snug"
                  style={{ color: C.grayMuted }}
                >
                  {option.hint}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onNext}
          disabled={value.length === 0}
          className="group inline-flex min-h-[3.25rem] items-center gap-2 rounded-2xl px-7 py-3.5 text-[16px] font-semibold text-white transition-all hover:shadow-[var(--shadow-pop)] disabled:cursor-not-allowed disabled:opacity-45"
          style={{ background: C.orange }}
        >
          Continuer
          <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
        </button>
        {value.length === 0 && (
          <span className="text-[13px]" style={{ color: C.grayMuted }}>
            Cochez au moins une intention.
          </span>
        )}
      </div>
    </div>
  );
}
