import { CadrageStep, CadrageTile } from './CadrageStep';
import { ETATS_CONSERVATION, type EtatConservation } from '@/constants/monument-options';

const HINTS: Record<EtatConservation, string> = {
  bon: "Le monument est globalement sain, même s'il demande des travaux d'entretien courants.",
  moyen: 'Des désordres existent mais ne menacent ni la structure ni le clos couvert.',
  mauvais: 'Des désordres significatifs affectent la structure ou le clos couvert.',
  peril: "Structure fragilisée, hors d'eau non assuré, effondrement partiel, désordres qui s'aggravent.",
};

interface PerilStepProps {
  /** `null` tant que la question n'a pas de réponse. */
  value: EtatConservation | null;
  onChange: (etatConservation: EtatConservation) => void;
  onNext: () => void;
  /** Absent quand l'écran ouvre le parcours : il n'y a rien derrière. */
  onBack?: () => void;
  /** Surtitre : « Nouveau monument », « Nouveau projet »… selon le parcours. */
  eyebrow: string;
  saving?: boolean;
}

/**
 * Écran de RATTRAPAGE de l'état du monument, en tête du wizard projet.
 *
 * À la création, l'état se saisit dans le formulaire du monument (étape 3,
 * champ requis) : cet écran ne sert donc qu'aux fiches créées avant que la
 * question n'existe — sans lui, elle ne serait plus jamais posée. Il décrit le
 * BIEN, pas un chantier : la réponse va sur le monument et tous ses projets la
 * partagent.
 *
 * Alimente `monument.etatConservation` sur ses quatre niveaux : les aides qui
 * le lisent (loto-patrimoine, mission-patrimoine,
 * region-bourgogne-franche-comte-mh, programme-patrimoine-roman) gatent
 * `{in: [mauvais, peril]}`, c'est donc bien la valeur choisie ici qui les
 * discrimine.
 */
export function PerilStep({
  value,
  onChange,
  onNext,
  onBack,
  eyebrow,
  saving,
}: PerilStepProps) {
  return (
    <CadrageStep
      eyebrow={eyebrow}
      title="Quel est l'état du monument ?"
      intro="En péril ou en mauvais état général : structure fragilisée, hors d'eau non assuré, effondrement partiel, désordres qui s'aggravent. Plusieurs dispositifs d'urgence ne s'adressent qu'à ces situations."
      onNext={onNext}
      onBack={onBack}
      nextDisabled={value === null}
      nextHint="Choisissez une réponse."
      saving={saving}
    >
      <div
        role="radiogroup"
        aria-label="Quel est l'état du monument ?"
        className="grid grid-cols-1 gap-2.5 sm:grid-cols-2"
      >
        {ETATS_CONSERVATION.map((etat) => (
          <CadrageTile
            key={etat.value}
            label={etat.label}
            hint={HINTS[etat.value]}
            selected={value === etat.value}
            onSelect={() => onChange(etat.value)}
          />
        ))}
      </div>
    </CadrageStep>
  );
}
