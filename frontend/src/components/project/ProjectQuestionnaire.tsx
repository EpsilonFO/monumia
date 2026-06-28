import { useEffect, useRef, useState } from 'react';
import { ArrowRight, ArrowLeft, Check, Loader2, Sparkles } from 'lucide-react';
import { C, SERIF } from '@/lib/brand';
import type { ProjectQuestionnaireAnswers, QcmQuestion } from '@/types';

interface ProjectQuestionnaireProps {
  /** Questions générées par le moteur d'aides (faits manquants du diagnostic). */
  questions: QcmQuestion[];
  value: ProjectQuestionnaireAnswers;
  onChange: (answers: ProjectQuestionnaireAnswers) => void;
  /** Appelé sur l'écran de fin, quand l'utilisateur lance le diagnostic. */
  onComplete: () => void;
  /** Vrai pendant l'enregistrement + le diagnostic (spinner sur le bouton final). */
  submitting?: boolean;
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
 * La dernière mène à un écran de fin avec le bouton « Lancer le diagnostic » (jamais
 * de lancement par accident). Données inchangées : `value` reste un Record id→option,
 * une question non répondue (« Je ne sais pas ») est gérée par le moteur.
 */
export function ProjectQuestionnaire({
  questions,
  value,
  onChange,
  onComplete,
  submitting,
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

  // Nettoyage du timer au démontage.
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
    // En revenant sur une question répondue, on focalise l'option choisie ; sinon la 1re.
    const targetId = value[current.id] ?? current.options[0]?.id;
    if (targetId) optionRefs.current[`${current.id}:${targetId}`]?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, onFinish]);

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
      <div
        key="finish"
        className={`flex flex-col items-center gap-4 rounded-2xl border px-6 py-10 text-center ${slideClass}`}
        style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' }}
      >
        <span
          className="flex h-16 w-16 items-center justify-center rounded-full"
          style={{ background: C.paleOrange }}
          aria-hidden
        >
          <Sparkles className="h-7 w-7" style={{ color: C.orange }} />
        </span>
        <h2
          ref={finishRef}
          tabIndex={-1}
          className="text-[clamp(1.4rem,3vw,1.9rem)] leading-tight outline-none"
          style={{ fontFamily: SERIF, color: C.ink }}
        >
          C&apos;est tout&nbsp;! 🎉
        </h2>
        <p className="max-w-sm text-[14px] leading-relaxed" style={{ color: C.grayFg }}>
          {answered > 0
            ? `Vous avez répondu à ${answered} question${answered > 1 ? 's' : ''}. Lançons le diagnostic pour découvrir vos aides.`
            : 'Pas de souci si vous avez passé des questions. Lançons le diagnostic pour découvrir vos aides.'}
        </p>
        <button
          type="button"
          onClick={onComplete}
          disabled={submitting}
          className="group mt-1 inline-flex items-center gap-2 rounded-xl px-6 py-3 text-[15px] font-semibold text-white transition-all hover:shadow-[var(--shadow-pop)] disabled:opacity-60"
          style={{ background: C.orange }}
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Analyse des aides en cours…
            </>
          ) : (
            <>
              Lancer le diagnostic
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

  return (
    <div className="space-y-6">
      {/* Progression « Question X sur Y » + barre */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-[12px] font-semibold">
          <span aria-live="polite" style={{ color: C.grayMuted }}>
            Question {index + 1} sur {total}
          </span>
          <span className="tabular-nums" style={{ color: C.orange }}>
            {pct}&nbsp;%
          </span>
        </div>
        <div
          className="h-1.5 w-full overflow-hidden rounded-full"
          style={{ background: C.border }}
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={index + 1}
        >
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{ width: `${pct}%`, background: C.orange }}
          />
        </div>
      </div>

      {/* Panneau de la question (glisse à chaque changement) */}
      <div key={index} className={slideClass}>
        <fieldset role="radiogroup" className="space-y-4">
          <legend className="mb-1 w-full">
            <span
              className="block text-[clamp(1.25rem,3vw,1.6rem)] leading-snug"
              style={{ fontFamily: SERIF, color: C.ink }}
            >
              {q!.question}
            </span>
          </legend>

          <div className="space-y-2.5">
            {q!.options.map((option, optionIndex) => {
              const selected = value[q!.id] === option.id;
              const refKey = `${q!.id}:${option.id}`;
              const roving = selected || (value[q!.id] === undefined && optionIndex === 0);
              return (
                <button
                  key={option.id}
                  ref={(el) => {
                    optionRefs.current[refKey] = el;
                  }}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  tabIndex={roving ? 0 : -1}
                  onClick={() => commit(option.id)}
                  onKeyDown={(e) => onOptionKeyDown(e, optionIndex)}
                  className="group flex min-h-14 w-full items-center gap-3.5 rounded-2xl border px-5 py-4 text-left text-[15px] transition-all duration-200 hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  style={{
                    borderColor: selected ? C.orange : C.border,
                    background: selected ? C.paleOrange : C.card,
                    color: C.ink,
                    boxShadow: selected ? 'var(--shadow-card)' : 'none',
                  }}
                >
                  <span
                    className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 transition-colors"
                    style={{
                      borderColor: selected ? C.orange : C.border,
                      background: selected ? C.orange : 'transparent',
                    }}
                  >
                    {selected && <Check className="h-3.5 w-3.5 text-white" strokeWidth={3} />}
                  </span>
                  <span className="leading-snug">{option.label}</span>
                </button>
              );
            })}
          </div>
        </fieldset>

        {/* Passer sans bloquer */}
        <div className="mt-3 flex justify-center">
          <button
            type="button"
            onClick={skip}
            className="text-[13px] underline-offset-2 transition-colors hover:underline"
            style={{ color: C.grayMuted }}
          >
            Je ne sais pas
          </button>
        </div>
      </div>

      {/* Navigation bas : précédent + réassurance */}
      <div className="flex items-center justify-between pt-1">
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
        <span className="text-[12px]" style={{ color: C.grayMuted }}>
          Vous pourrez tout modifier plus tard
        </span>
      </div>
    </div>
  );
}
