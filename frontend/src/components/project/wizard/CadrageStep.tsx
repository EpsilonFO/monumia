import type { ReactNode } from 'react';
import { CarteReponse, EcranQuestion } from './EcranQuestion';

interface CadrageStepProps {
  /** Rubrique au-dessus de la question : le libellé de l'étape dans la colonne. */
  rubrique: string;
  title: string;
  /** Sous le titre : « Plusieurs réponses possibles. », par exemple. */
  consigne?: string;
  /** Encart « Bon à savoir ». */
  pourquoi: string;
  /** Entre l'encart et les réponses. */
  avantReponses?: ReactNode;
  /** Les réponses (des `CadrageTile`), posées dans la grille de l'écran. */
  children: ReactNode;
  multiple?: boolean;
  onNext: () => void;
  /** Absent quand l'écran ouvre le parcours. */
  onBack?: () => void;
  /** L'échappatoire de l'étape, dans la barre du bas (« Pas encore déterminé »). */
  onPasser?: () => void;
  libellePasser?: string;
  /** Tant qu'aucune réponse n'est donnée, « Continuer » reste inerte. */
  nextDisabled?: boolean;
  /** Pourquoi « Continuer » est inerte (dit aux lecteurs d'écran). */
  nextHint?: string;
  /** Vrai pendant un enregistrement (roue sur le bouton). */
  saving?: boolean;
  /** « Vous pourrez modifier vos réponses plus tard », quand c'est vrai. */
  modifiablePlusTard?: boolean;
}

/**
 * Écran de cadrage du wizard projet, au même format que les questions du
 * moteur (`EcranQuestion`) : rubrique, question, encart « Bon à savoir », réponses
 * en cartes, barre de navigation. Une étape de cadrage peut renommer le lien
 * « Je ne sais pas, passer » de la barre du bas : son échappatoire (« Pas encore
 * déterminé ») est une réponse enregistrée, pas une question sautée.
 */
export function CadrageStep({
  rubrique,
  title,
  consigne,
  pourquoi,
  avantReponses,
  children,
  multiple,
  onNext,
  onBack,
  onPasser,
  libellePasser,
  nextDisabled,
  nextHint,
  saving,
  modifiablePlusTard,
}: CadrageStepProps) {
  return (
    <EcranQuestion
      rubrique={rubrique}
      titre={title}
      consigne={consigne}
      pourquoi={pourquoi}
      avantReponses={avantReponses}
      multiple={multiple}
      gele={saving}
      onPrecedent={onBack}
      onPasser={onPasser}
      libellePasser={libellePasser}
      onContinuer={onNext}
      continuerDesactive={nextDisabled}
      continuerIndice={nextHint}
      enCours={saving}
      modifiablePlusTard={modifiablePlusTard}
    >
      {children}
    </EcranQuestion>
  );
}

interface CadrageTileProps {
  label: string;
  /** Précision du libellé, en infobulle au survol de la carte. */
  hint?: string;
  selected: boolean;
  /** Case carrée (choix multiple) plutôt que ronde (choix exclusif). */
  multiple?: boolean;
  onSelect: () => void;
}

/** Réponse cochable d'un écran de cadrage : la carte du questionnaire. */
export function CadrageTile({ label, hint, selected, multiple, onSelect }: CadrageTileProps) {
  return (
    <CarteReponse
      label={label}
      description={hint}
      selected={selected}
      multiple={multiple}
      onSelect={onSelect}
    />
  );
}
