import { useEffect, useRef, type KeyboardEvent } from 'react';
import { isUnknownAnswer } from './unknownAnswer';
import { CarteReponse } from './EcranQuestion';
import { reponsesAffichees, reponsesChoisies, toggleMulti } from '@/lib/question-reponse';
import type { QcmOption, QcmQuestion } from '@/types';

interface ReponsesQuestionProps {
  question: QcmQuestion;
  /** Réponse courante : un id (choix simple), une liste d'ids (choix multiple). */
  value: string | string[] | undefined;
  /** Nouvelle réponse ; `undefined` quand la dernière case est décochée. */
  onAnswer: (answer: string | string[] | undefined) => void;
  /** Pose le focus sur la réponse cochée (ou la première) à l'arrivée. */
  autoFocus?: boolean;
}

/**
 * Les cartes de réponse d'une question du moteur, dans le wizard : à poser dans
 * la grille d'`EcranQuestion`.
 *
 * Le composant POSSÈDE les refs de ses boutons, le parcours au clavier (flèches,
 * tabindex itinérant) et le focus initial, comme `QuestionOptions`, qui garde
 * l'ancien dessin pour la fiche d'une aide (`AideDetails`).
 */
export function ReponsesQuestion({ question, value, onAnswer, autoFocus }: ReponsesQuestionProps) {
  const optionRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const chosen = reponsesChoisies(value);
  const multiple = !!question.multiple;
  const ordre = reponsesAffichees(question);

  useEffect(() => {
    if (!autoFocus) return;
    const cible = chosen[0] ?? ordre[0]?.id;
    if (cible) optionRefs.current[cible]?.focus();
    // Le focus se pose à l'arrivée sur la question, pas à chaque clic.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question.id, autoFocus]);

  const choisir = (option: QcmOption) => {
    if (!multiple) {
      onAnswer(option.id);
      return;
    }
    const next = toggleMulti(question, chosen, option);
    onAnswer(next.length === 0 ? undefined : next);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>, rang: number) => {
    const suivant = e.key === 'ArrowDown' || e.key === 'ArrowRight';
    const precedent = e.key === 'ArrowUp' || e.key === 'ArrowLeft';
    if (!suivant && !precedent) return;
    e.preventDefault();
    const n = suivant ? (rang + 1) % ordre.length : (rang - 1 + ordre.length) % ordre.length;
    optionRefs.current[ordre[n].id]?.focus();
  };

  return (
    <>
      {ordre.map((option, rang) => {
        const selected = chosen.includes(option.id);
        // Tabindex itinérant : seule la réponse cochée (ou la première) est
        // atteinte par Tab, les flèches parcourent les autres.
        const active = selected || (chosen.length === 0 && rang === 0);
        return (
          <CarteReponse
            key={option.id}
            label={option.label}
            description={option.description}
            selected={selected}
            multiple={multiple}
            nsp={isUnknownAnswer(option)}
            onSelect={() => choisir(option)}
            tabIndex={active ? 0 : -1}
            onKeyDown={(e) => onKeyDown(e, rang)}
            buttonRef={(el) => {
              optionRefs.current[option.id] = el;
            }}
          />
        );
      })}
    </>
  );
}
