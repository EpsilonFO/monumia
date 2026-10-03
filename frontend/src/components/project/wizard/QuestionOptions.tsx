import { useEffect, useRef } from 'react';
import { AnswerCard } from './AnswerCard';
import { SkipCard } from './SkipCard';
import { QuestionHelp } from './QuestionHelp';
import { isUnknownAnswer } from './unknownAnswer';
import { displayOrder, toggleMulti } from '@/lib/question-reponse';
import { C, SERIF } from '@/lib/brand';
import { cn } from '@/lib/utils';
import type { QcmQuestion } from '@/types';

interface QuestionOptionsProps {
  question: QcmQuestion;
  /** Réponse courante : un id (choix simple), une liste d'ids (choix multiple). */
  value: string | string[] | undefined;
  /**
   * Nouvelle réponse. `undefined` = la question redevient sans réponse (dernière
   * case décochée, ou « Passer cette question » quand `onSkip` n'est pas fourni).
   */
  onAnswer: (answer: string | string[] | undefined) => void;
  /**
   * Geste « Passer cette question » : la carte pointillée n'est rendue que s'il
   * est fourni, et seulement quand le moteur n'a pas donné d'échappatoire à lui.
   * Un même prop pour l'affichage ET l'action : impossible d'afficher un bouton
   * qui ne ferait rien.
   */
  onSkip?: () => void;
  /** Pose le focus sur la réponse cochée (ou la première) au montage. */
  autoFocus?: boolean;
  /** Version resserrée : sur une carte d'aide, pas au milieu du questionnaire. */
  compact?: boolean;
  /** Pendant l'enregistrement d'une réponse : on n'en accepte pas une seconde. */
  disabled?: boolean;
}

/**
 * Le bloc « une question et ses réponses », partout où on le pose.
 *
 * Extrait du questionnaire pour servir aussi sur la CARTE et la FICHE d'une
 * aide : depuis que le tronc commun ne pose que les questions partagées, celles
 * qui ne servent qu'une aide se posent là où l'utilisateur regarde cette aide.
 * Le composant POSSÈDE les refs de ses boutons, le parcours au clavier et le
 * focus initial — des refs sur des boutons ne peuvent pas rester chez le
 * parent. Ce qui reste au parent : le « Continuer » et l'encart d'une réponse
 * écartante, qui relèvent du parcours, pas de la question.
 */
export function QuestionOptions({
  question,
  value,
  onAnswer,
  onSkip,
  autoFocus,
  compact,
  disabled,
}: QuestionOptionsProps) {
  const optionRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const chosen = Array.isArray(value) ? value : typeof value === 'string' ? [value] : [];
  const multiple = !!question.multiple;

  // Les options « je ne sais pas » du moteur descendent en bas de la liste,
  // rendues comme le bouton « Passer cette question » : même forme pour la même
  // intention. Quand le moteur n'en fournit aucune, on propose notre « passer ».
  const answerOptions = question.options.filter((o) => !isUnknownAnswer(o));
  const unknownOptions = question.options.filter(isUnknownAnswer);
  // En choix multiple, « passer » effacerait des cases cochées : on ne le
  // propose plus dès qu'il y en a (« Continuer » prend le relais côté parent).
  const showSkipCard = !!onSkip && unknownOptions.length === 0 && (!multiple || chosen.length === 0);

  useEffect(() => {
    if (!autoFocus) return;
    const cible = chosen[0] ?? question.options[0]?.id;
    if (cible) optionRefs.current[`${question.id}:${cible}`]?.focus();
    // Le focus se pose à l'arrivée sur la question, pas à chaque frappe.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question.id, autoFocus]);

  const choisir = (optionId: string) => {
    if (disabled) return;
    const option = question.options.find((o) => o.id === optionId);
    if (!option) return;
    if (!multiple) {
      onAnswer(option.id);
      return;
    }
    const next = toggleMulti(question, chosen, option);
    onAnswer(next.length === 0 ? undefined : next);
  };

  const onOptionKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>, optionIndex: number) => {
    const isNext = e.key === 'ArrowDown' || e.key === 'ArrowRight';
    const isPrev = e.key === 'ArrowUp' || e.key === 'ArrowLeft';
    if (!isNext && !isPrev) return;
    e.preventDefault();
    const order = displayOrder(question);
    const n = isNext
      ? (optionIndex + 1) % order.length
      : (optionIndex - 1 + order.length) % order.length;
    optionRefs.current[`${question.id}:${order[n].id}`]?.focus();
  };

  return (
    <fieldset
      role={multiple ? 'group' : 'radiogroup'}
      disabled={disabled}
      className={cn(compact ? 'space-y-2.5' : 'space-y-4', disabled && 'opacity-60')}
    >
      {/* La légende ne porte QUE la question : c'est elle qui nomme le groupe de
          boutons radio pour les lecteurs d'écran. La note explicative vit à
          côté, où elle peut être repliée. */}
      <legend className="w-full">
        <span
          className={cn(
            'block leading-snug',
            compact ? 'text-[17px] font-semibold' : 'text-[clamp(1.25rem,2.8vw,1.6rem)]',
          )}
          style={compact ? { color: C.ink } : { fontFamily: SERIF, color: C.ink }}
        >
          {question.question}
        </span>
        {/* La consigne doit être lue AVANT de cliquer : la forme carrée des
            cases ne suffit pas à dire qu'on peut en cocher plusieurs. */}
        {multiple && (
          <span
            className={cn('block font-semibold', compact ? 'mt-1 text-[14px]' : 'mt-1.5 text-[15px]')}
            style={{ color: C.orange }}
          >
            Plusieurs réponses possibles
          </span>
        )}
      </legend>

      {question.help && <QuestionHelp text={question.help} compact={compact} />}

      <div
        className={cn(
          'grid gap-2.5',
          answerOptions.length > 3 ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-1',
        )}
      >
        {answerOptions.map((option, optionIndex) => {
          const selected = chosen.includes(option.id);
          return (
            <AnswerCard
              key={option.id}
              option={option}
              selected={selected}
              roving={selected || (chosen.length === 0 && optionIndex === 0)}
              multiple={multiple}
              onSelect={() => choisir(option.id)}
              onKeyDown={(e) => onOptionKeyDown(e, optionIndex)}
              buttonRef={(el) => {
                optionRefs.current[`${question.id}:${option.id}`] = el;
              }}
            />
          );
        })}
      </div>

      {/* Les « je ne sais pas » du moteur : mêmes cartes pointillées que le
          « passer », mais ce sont de vraies réponses — elles restent dans le
          groupe radio et se cochent. */}
      {unknownOptions.map((option, unknownIndex) => {
        const selected = chosen.includes(option.id);
        return (
          <SkipCard
            key={option.id}
            label={option.label}
            asOption
            selected={selected}
            roving={
              selected || (chosen.length === 0 && answerOptions.length === 0 && unknownIndex === 0)
            }
            multiple={multiple}
            onSelect={() => choisir(option.id)}
            onKeyDown={(e) => onOptionKeyDown(e, answerOptions.length + unknownIndex)}
            buttonRef={(el) => {
              optionRefs.current[`${question.id}:${option.id}`] = el;
            }}
          />
        );
      })}

      {/* En choix simple, « passer » reste offert y compris sur une question
          déjà répondue où l'on revient — c'est le seul moyen de se dédire. */}
      {showSkipCard && <SkipCard label="Passer cette question" onSelect={() => onSkip?.()} />}
    </fieldset>
  );
}
