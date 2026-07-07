import { useEffect, useRef, useState } from 'react';
import { ArrowRight, ArrowLeft, Loader2 } from 'lucide-react';
import { AllClear } from '@/components/illustrations';
import { AnswerCard } from '@/components/project/wizard/AnswerCard';
import { isUnknownAnswer } from '@/components/project/wizard/unknownAnswer';
import { C, SERIF } from '@/lib/brand';
import { cn } from '@/lib/utils';
import type { ProjectQuestionnaireAnswers, QcmQuestion } from '@/types';

interface ProjectQuestionnaireProps {
  /** Questions générées par le moteur d'aides (faits manquants du diagnostic). */
  questions: QcmQuestion[];
  value: ProjectQuestionnaireAnswers;
  onChange: (answers: ProjectQuestionnaireAnswers) => void;
  /** Appelé sur l'écran de fin, quand l'utilisateur valide. */
  onComplete: () => void;
  /** Vrai pendant l'enregistrement + le diagnostic (spinner sur le bouton final). */
  submitting?: boolean;
  /** Libellé du bouton final. */
  completeLabel?: string;
  /** Remonte la position courante (rail + header mobile du shell). */
  onProgress?: (progress: { index: number; total: number }) => void;
}

/** Délai avant l'auto-avance : laisse voir sa réponse se cocher. */
const ADVANCE_MS = 420;

function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' &&
    !!window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

/**
 * Questionnaire du moteur d'aides, posé **une question à la fois** (style Doctolib).
 * On clique une réponse → elle se coche → la question suivante glisse automatiquement.
 * La dernière mène à un écran de fin avec le bouton final (jamais de lancement par accident).
 * Données inchangées : `value` reste un Record id→option ; une question non répondue
 * (« Je ne sais pas ») est gérée par le moteur.
 */
export function ProjectQuestionnaire({
  questions,
  value,
  onChange,
  onComplete,
  submitting,
  completeLabel = 'Lancer le diagnostic',
  onProgress,
}: ProjectQuestionnaireProps) {
  const total = questions.length;
  const [index, setIndex] = useState(0);
  const [dir, setDir] = useState<'fwd' | 'back'>('fwd');
  const advanceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const optionRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const finishRef = useRef<HTMLHeadingElement | null>(null);

  const onFinish = index >= total;
  const q = onFinish ? null : questions[index];

  const clearTimer = () => {
    if (advanceTimer.current) {
      clearTimeout(advanceTimer.current);
      advanceTimer.current = null;
    }
  };

  useEffect(() => clearTimer, []);

  // Focus à chaque changement d'écran (accessibilité + clavier).
  useEffect(() => {
    clearTimer();
    if (onFinish) {
      finishRef.current?.focus();
      return;
    }
    const current = questions[index];
    if (!current) return;
    const targetId = value[current.id] ?? current.options[0]?.id;
    if (targetId) optionRefs.current[`${current.id}:${targetId}`]?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, onFinish]);

  // Le shell (rail desktop + header mobile) affiche la progression : on la
  // lui remonte à chaque changement d'écran (index === total sur la fin).
  useEffect(() => {
    onProgress?.({ index: Math.min(index, total), total });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, total]);

  const goNext = () => {
    clearTimer();
    setDir('fwd');
    setIndex((i) => Math.min(i + 1, total));
  };

  const goBack = () => {
    clearTimer();
    setDir('back');
    setIndex((i) => Math.max(i - 1, 0));
  };

  /** Sélectionne une réponse puis avance automatiquement après un court délai. */
  const commit = (optionId: string) => {
    if (!q) return;
    onChange({ ...value, [q.id]: optionId });
    clearTimer();
    advanceTimer.current = setTimeout(goNext, prefersReducedMotion() ? 180 : ADVANCE_MS);
  };

  /** « Je ne sais pas » : on efface l'éventuelle réponse et on avance (le moteur gère). */
  const skip = () => {
    if (!q) return;
    if (value[q.id] !== undefined) {
      const next = { ...value };
      delete next[q.id];
      onChange(next);
    }
    goNext();
  };

  const onOptionKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>, optionIndex: number) => {
    if (!q) return;
    const isNext = e.key === 'ArrowDown' || e.key === 'ArrowRight';
    const isPrev = e.key === 'ArrowUp' || e.key === 'ArrowLeft';
    if (!isNext && !isPrev) return;
    e.preventDefault();
    const n = isNext
      ? (optionIndex + 1) % q.options.length
      : (optionIndex - 1 + q.options.length) % q.options.length;
    optionRefs.current[`${q.id}:${q.options[n].id}`]?.focus();
  };

  const slideClass = dir === 'fwd' ? 'q-in-fwd' : 'q-in-back';

  // ─── Écran de fin ───
  if (onFinish) {
    const answered = questions.filter((qq) => value[qq.id] !== undefined).length;
    return (
      <div className={cn('flex flex-col items-center gap-5 py-10 text-center', slideClass)}>
        <AllClear />
        <h2
          ref={finishRef}
          tabIndex={-1}
          className="text-[clamp(1.5rem,3.4vw,2rem)] leading-tight outline-none"
          style={{ fontFamily: SERIF, color: C.ink }}
        >
          C&rsquo;est tout&nbsp;!
        </h2>
        <p className="max-w-sm text-[15px] leading-relaxed" style={{ color: C.grayFg }}>
          {answered > 0
            ? `Vous avez répondu à ${answered} question${answered > 1 ? 's' : ''}. `
            : 'Pas de souci si vous avez passé des questions. '}
          On met à jour vos aides.
        </p>
        <button
          type="button"
          onClick={onComplete}
          disabled={submitting}
          className="group mt-1 inline-flex min-h-[3.25rem] items-center gap-2 rounded-2xl px-7 py-3.5 text-[16px] font-semibold text-white transition-all hover:shadow-[var(--shadow-pop)] disabled:opacity-60"
          style={{ background: C.orange }}
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Analyse des aides en cours…
            </>
          ) : (
            <>
              {completeLabel}
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </>
          )}
        </button>
        {!submitting && (
          <button
            type="button"
            onClick={goBack}
            className="inline-flex items-center gap-1.5 text-[13px] font-medium underline-offset-2 hover:underline"
            style={{ color: C.grayMuted }}
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Revoir mes réponses
          </button>
        )}
      </div>
    );
  }

  // ─── Une question à la fois ───
  // La barre reflète la position courante (jamais 0 % sur la 1re question).
  const pct = Math.round(((index + 1) / total) * 100);
  // Le moteur fournit souvent une option « Je ne sais pas » native : on évite
  // alors de la dupliquer en bas.
  const showSkipCard = !q!.options.some(isUnknownAnswer);

  return (
    <div>
      {/* Barre fine de progression, en tête de scène. */}
      <div className="pb-4">
        <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-[0.18em]">
          <span aria-live="polite" style={{ color: C.orange }}>
            Question {index + 1} <span style={{ color: C.grayMuted }}>sur {total}</span>
          </span>
          <span
            className="rounded-full px-2 py-0.5 tabular-nums tracking-normal"
            style={{ background: 'var(--secondary)', color: C.blue }}
          >
            {pct}&nbsp;%
          </span>
        </div>
        <div
          className="mt-2 h-1.5 w-full overflow-hidden rounded-full"
          style={{ background: C.border }}
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={index + 1}
        >
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${pct}%`,
              background: 'linear-gradient(90deg, var(--accent), var(--orange-vif))',
            }}
          />
        </div>
      </div>

      {/* Question (glisse à chaque changement) */}
      <div key={index} className={cn(slideClass, 'pb-1')}>
        <fieldset role="radiogroup" className="space-y-4">
          <legend className="w-full">
            <span
              className="block text-[clamp(1.25rem,2.8vw,1.6rem)] leading-snug"
              style={{ fontFamily: SERIF, color: C.ink }}
            >
              {q!.question}
            </span>
          </legend>

          <div
            className={cn(
              'grid gap-2.5',
              q!.options.length > 3 ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-1',
            )}
          >
            {q!.options.map((option, optionIndex) => {
              const selected = value[q!.id] === option.id;
              const refKey = `${q!.id}:${option.id}`;
              const roving = selected || (value[q!.id] === undefined && optionIndex === 0);
              return (
                <AnswerCard
                  key={option.id}
                  option={option}
                  optionIndex={optionIndex}
                  selected={selected}
                  roving={roving}
                  onSelect={() => commit(option.id)}
                  onKeyDown={(e) => onOptionKeyDown(e, optionIndex)}
                  buttonRef={(el) => {
                    optionRefs.current[refKey] = el;
                  }}
                />
              );
            })}
          </div>

          {showSkipCard && (
            <button
              type="button"
              onClick={skip}
              className="w-full rounded-2xl border border-dashed px-5 py-3 text-[14px] font-medium transition-colors hover:border-warning hover:bg-warning-muted"
              style={{ borderColor: C.border, color: C.grayFg }}
            >
              Je ne sais pas — passer cette question
            </button>
          )}
        </fieldset>
      </div>

      {/* Navigation bas */}
      <div
        className="mt-3 flex items-center justify-between border-t py-3"
        style={{ borderColor: C.border }}
      >
        <button
          type="button"
          onClick={goBack}
          disabled={index === 0}
          className="inline-flex min-h-11 items-center gap-1.5 text-[14px] font-medium transition-opacity disabled:pointer-events-none disabled:opacity-0"
          style={{ color: C.grayFg }}
        >
          <ArrowLeft className="h-4 w-4" />
          Précédent
        </button>
        <span className="hidden text-[12px] sm:block" style={{ color: C.grayMuted }}>
          Vous pourrez refaire ce questionnaire plus tard
        </span>
      </div>
    </div>
  );
}
