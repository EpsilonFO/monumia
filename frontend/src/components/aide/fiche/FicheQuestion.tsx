import { useId, useState } from 'react';
import { Ico } from './Ico';
import { isUnknownAnswer } from '@/components/project/wizard/unknownAnswer';
import { TexteAide } from '@/components/shared/TexteAide';
import { displayOrder, toggleMulti } from '@/lib/question-reponse';
import type { QcmQuestion } from '@/types';

/** Au-delà, les boutons passent sous la question au lieu de la border. */
const LIBELLE_COURT = 14;

/**
 * Une question du diagnostic, dans la forme de la maquette : la question à
 * gauche, ses réponses en boutons à droite (ou dessous, dès qu'elles sont
 * nombreuses ou longues). C'est une vraie question du moteur, partagée par
 * toutes les aides qui la posent : y répondre ici met à jour tout le projet.
 *
 * L'aide contextuelle de la question (`help`) se replie derrière un petit « i » :
 * la question se lit seule, en plus gros, et le détail vient à la demande.
 *
 * Sans `onAnswer`, la question reste lisible mais ses boutons sont inertes
 * (collaborateur sans droit d'écriture).
 */
export function FicheQuestion({
  question,
  value,
  onAnswer,
  disabled,
}: {
  question: QcmQuestion;
  value: string | string[] | undefined;
  onAnswer?: (answer: string | string[] | undefined) => void;
  disabled?: boolean;
}) {
  const choisies = Array.isArray(value) ? value : typeof value === 'string' ? [value] : [];
  const multiple = !!question.multiple;
  const options = displayOrder(question);
  const large =
    options.length > 3 || options.some((o) => o.label.length > LIBELLE_COURT || o.description);
  const inerte = disabled || !onAnswer;
  const [aideOuverte, setAideOuverte] = useState(false);
  const aideId = useId();

  const choisir = (id: string) => {
    const option = question.options.find((o) => o.id === id);
    if (inerte || !option) return;
    if (!multiple) return onAnswer(option.id);
    const suite = toggleMulti(question, choisies, option);
    onAnswer(suite.length ? suite : undefined);
  };

  return (
    <div className={`q${choisies.length ? ' answered' : ''}${large ? ' wide' : ''}`}>
      <div className="q-t">
        <p>
          {question.question}
          {question.help && (
            <button
              type="button"
              className={aideOuverte ? 'q-info on' : 'q-info'}
              aria-expanded={aideOuverte}
              aria-controls={aideId}
              aria-label={aideOuverte ? "Masquer l'explication" : 'Afficher une explication'}
              title={aideOuverte ? "Masquer l'explication" : 'En savoir plus'}
              onClick={(e) => {
                e.stopPropagation();
                setAideOuverte((o) => !o);
              }}
            >
              <Ico nom="info" />
            </button>
          )}
        </p>
        {multiple && <span className="multi">Plusieurs réponses possibles</span>}
        {question.help && (
          <TexteAide id={aideId} hidden={!aideOuverte} texte={question.help} className="q-aide" />
        )}
      </div>
      <div className="yn" role={multiple ? 'group' : 'radiogroup'} aria-label="Réponse">
        {options.map((o) => (
          <button
            key={o.id}
            type="button"
            role={multiple ? 'checkbox' : 'radio'}
            aria-checked={choisies.includes(o.id)}
            className={isUnknownAnswer(o) ? 'unknown' : undefined}
            disabled={inerte}
            onClick={(e) => {
              e.stopPropagation();
              choisir(o.id);
            }}
          >
            {o.label}
            {o.description && <small>{o.description}</small>}
          </button>
        ))}
      </div>
    </div>
  );
}
