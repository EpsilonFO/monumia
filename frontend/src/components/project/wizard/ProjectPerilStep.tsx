import { CadrageStep, CadrageTile } from './CadrageStep';

interface ProjectPerilStepProps {
  /** `null` tant que la question n'a pas de réponse. */
  value: boolean | null;
  onChange: (peril: boolean) => void;
  onNext: () => void;
  onBack: () => void;
  /** Surtitre : « Nouveau projet » ou « Questionnaire » selon le parcours. */
  eyebrow: string;
  saving?: boolean;
}

/**
 * Écran « Le monument est-il en péril ? » de l'étape « Votre projet ».
 *
 * Alimente `monument.etat_conservation`, réduit à ce seul signal : les quatre
 * aides qui le lisent (loto-patrimoine, mission-patrimoine,
 * region-bourgogne-franche-comte-mh, programme-patrimoine-roman) gatent toutes
 * `{in: [mauvais, peril]}`. Répondre oui persiste `peril` et les libère,
 * répondre non persiste `bon` et les écarte : la discrimination des quatre
 * niveaux d'état est donc intégralement préservée par une question binaire.
 */
export function ProjectPerilStep({
  value,
  onChange,
  onNext,
  onBack,
  eyebrow,
  saving,
}: ProjectPerilStepProps) {
  return (
    <CadrageStep
      eyebrow={eyebrow}
      title="Le monument est-il en péril ?"
      intro="En péril ou en mauvais état général : structure fragilisée, hors d'eau non assuré, effondrement partiel, désordres qui s'aggravent. Plusieurs dispositifs d'urgence ne s'adressent qu'à ces situations."
      onNext={onNext}
      onBack={onBack}
      nextDisabled={value === null}
      nextHint="Choisissez une réponse."
      saving={saving}
    >
      <div
        role="radiogroup"
        aria-label="Le monument est-il en péril ?"
        className="grid grid-cols-1 gap-2.5 sm:grid-cols-2"
      >
        <CadrageTile
          label="Oui"
          hint="Le monument est en péril ou en mauvais état général."
          selected={value === true}
          onSelect={() => onChange(true)}
        />
        <CadrageTile
          label="Non"
          hint="Le monument est globalement sain, même s'il demande des travaux."
          selected={value === false}
          onSelect={() => onChange(false)}
        />
      </div>
    </CadrageStep>
  );
}
