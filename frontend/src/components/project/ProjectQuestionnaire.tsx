import { useRef } from 'react';
import { Check } from 'lucide-react';
import { C, SERIF } from '@/lib/brand';
import { QUESTIONNAIRE_QUESTIONS } from '@/types';
import type { ProjectQuestionnaireAnswers } from '@/types';

interface ProjectQuestionnaireProps {
  value: ProjectQuestionnaireAnswers;
  onChange: (answers: ProjectQuestionnaireAnswers) => void;
}

export function ProjectQuestionnaire({ value, onChange }: ProjectQuestionnaireProps) {
  /** Refs to all radio buttons, keyed by `${questionId}:${optionId}`. */
  const buttonRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  const select = (questionId: string, optionId: string) => {
    onChange({ ...value, [questionId]: optionId });
  };

  const handleKeyDown = (
    e: React.KeyboardEvent<HTMLButtonElement>,
    questionId: string,
    optionIndex: number,
    options: { id: string }[],
  ) => {
    const isNext = e.key === 'ArrowDown' || e.key === 'ArrowRight';
    const isPrev = e.key === 'ArrowUp' || e.key === 'ArrowLeft';
    if (!isNext && !isPrev) return;
    e.preventDefault();

    const nextIndex = isNext
      ? (optionIndex + 1) % options.length
      : (optionIndex - 1 + options.length) % options.length;
    const nextOptionId = options[nextIndex].id;

    // Move selection
    select(questionId, nextOptionId);

    // Move focus
    const key = `${questionId}:${nextOptionId}`;
    buttonRefs.current[key]?.focus();
  };

  return (
    <div className="space-y-8">
      {QUESTIONNAIRE_QUESTIONS.map((q, index) => (
        /* role="radiogroup" is valid on <fieldset>; the <legend> provides the accessible name. */
        <fieldset key={q.id} role="radiogroup" className="space-y-3">
          <legend className="flex items-baseline gap-2">
            <span
              className="text-[13px] font-semibold tabular-nums"
              style={{ color: C.orange }}
            >
              {String(index + 1).padStart(2, '0')}
            </span>
            <span
              className="text-[18px] leading-snug"
              style={{ fontFamily: SERIF, color: C.ink }}
            >
              {q.question}
            </span>
          </legend>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {q.options.map((option, optionIndex) => {
              const selected = value[q.id] === option.id;
              const refKey = `${q.id}:${option.id}`;
              return (
                <button
                  key={option.id}
                  ref={(el) => { buttonRefs.current[refKey] = el; }}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => select(q.id, option.id)}
                  onKeyDown={(e) => handleKeyDown(e, q.id, optionIndex, q.options)}
                  className="flex items-center gap-3 rounded-lg border px-4 py-3 text-left text-[14px] transition-all duration-200"
                  style={{
                    borderColor: selected ? C.orange : C.border,
                    background: selected ? C.paleOrange : C.card,
                    color: C.ink,
                  }}
                >
                  <span
                    className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border transition-colors"
                    style={{
                      borderColor: selected ? C.orange : C.border,
                      background: selected ? C.orange : 'transparent',
                    }}
                  >
                    {selected && <Check className="h-3 w-3 text-white" strokeWidth={3} />}
                  </span>
                  <span className="leading-snug">{option.label}</span>
                </button>
              );
            })}
          </div>
        </fieldset>
      ))}
    </div>
  );
}
