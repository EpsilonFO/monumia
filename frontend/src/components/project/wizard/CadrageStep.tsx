import type { ReactNode } from 'react';
import { CarteReponse, EcranQuestion } from './EcranQuestion';

interface CadrageStepProps {
  /** Rubrique au-dessus de la question : le libellé de l'étape dans la colonne. */
  rubrique: string;
  title: string;
  /** Sous le titre : « Plusieurs réponses possibles. », par exemple. */
  consigne?: string;
  /** Encart « Pourquoi on vous le demande ». */
  pourquoi: string;
  /** Entre l'encart et les réponses. */
  avantReponses?: ReactNode;
  /** Les réponses (des `CadrageTile`), posées dans la grille à deux colonnes. */
  children: ReactNode;
  multiple?: boolean;
  /** Longue liste de réponses sans précision : cartes serrées. */
  serre?: boolean;
  onNext: () => void;
  /** Absent quand l'écran ouvre le parcours. */
  onBack?: () => void;
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
 * moteur (`EcranQuestion`) : rubrique, question, encart « Pourquoi », réponses
 * en cartes, barre de navigation. Pas de « Je ne sais pas, passer » ici : les
 * étapes de cadrage portent chacune leur propre « pas encore déterminé », qui
 * est une réponse enregistrée.
 */
export function CadrageStep({
  rubrique,
  title,
  consigne,
  pourquoi,
  avantReponses,
  children,
  multiple,
  serre,
  onNext,
  onBack,
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
      serre={serre}
      gele={saving}
      onPrecedent={onBack}
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
  /** Précision sous le libellé. */
  hint?: string;
  selected: boolean;
  /** Case carrée (choix multiple) plutôt que ronde (choix exclusif). */
  multiple?: boolean;
  /** Réponse à part, sur toute la largeur (« Pas encore déterminé »…). */
  large?: boolean;
  onSelect: () => void;
}

/** Réponse cochable d'un écran de cadrage : la carte du questionnaire. */
export function CadrageTile({ label, hint, selected, multiple, large, onSelect }: CadrageTileProps) {
  return (
    <CarteReponse
      label={label}
      description={hint}
      selected={selected}
      multiple={multiple}
      large={large}
      onSelect={onSelect}
    />
  );
}
