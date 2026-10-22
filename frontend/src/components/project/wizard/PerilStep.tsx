import { useTranslation } from 'react-i18next';
import { CadrageStep, CadrageTile } from './CadrageStep';
import { PERIL_RATTRAPAGE_STEP } from './etapes';
import { ETATS_CONSERVATION, type EtatConservation } from '@/constants/monument-options';

interface PerilStepProps {
  /** `null` tant que la question n'a pas de réponse. */
  value: EtatConservation | null;
  onChange: (etatConservation: EtatConservation) => void;
  onNext: () => void;
  /** Absent quand l'écran ouvre le parcours : il n'y a rien derrière. */
  onBack?: () => void;
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
  saving,
}: PerilStepProps) {
  const { t } = useTranslation('project');
  return (
    <CadrageStep
      rubrique={PERIL_RATTRAPAGE_STEP.label}
      title={t('PerilStep.titre')}
      pourquoi={t('PerilStep.pourquoi')}
      onNext={onNext}
      onBack={onBack}
      nextDisabled={value === null}
      nextHint={t('consignes.choisissezUneReponse')}
      saving={saving}
    >
      {ETATS_CONSERVATION.map((etat) => (
        <CadrageTile
          key={etat.value}
          label={etat.label}
          hint={t(`PerilStep.indices.${etat.value}`)}
          selected={value === etat.value}
          onSelect={() => onChange(etat.value)}
        />
      ))}
    </CadrageStep>
  );
}
