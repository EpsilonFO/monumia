import { useTranslation } from 'react-i18next';
import { RAISON_CHOIX, type Raison } from '@/constants/raisons';
import { CadrageStep, CadrageTile } from './CadrageStep';
import { INTENTION_STEP } from './etapes';

interface ProjectIntentStepProps {
  /** Toujours une liste, mais d'au plus une intention : la forme `_raisons`
   *  attendue par le questionnaire et le moteur n'a pas bougé. */
  value: string[];
  onChange: (raisons: string[]) => void;
  onNext: () => void;
}

/**
 * Étape « Votre projet » : ce que le propriétaire veut faire, sur les finalités
 * du catalogue proposées (`RAISON_CHOIX`). C'est le seul filtre en amont du
 * questionnaire : sans lui, les faits manquants de TOUTES les aides candidates
 * deviennent des questions, y compris celles d'aides sans rapport avec le
 * projet. Choix EXCLUSIF : un chantier a une finalité, et les autres se
 * traitent dans un autre projet du même monument.
 *
 * Pas de « Question précédente » : c'est le premier écran du parcours. Pas de
 * « modifiable plus tard » non plus : « Tout refaire » garde l'intention du
 * projet (cf. `intentionVerrouillee` dans `ProjetWizardPage`).
 */
export function ProjectIntentStep({ value, onChange, onNext }: ProjectIntentStepProps) {
  const { t } = useTranslation('project');
  const select = (raison: Raison) => {
    onChange([raison]);
  };

  return (
    <CadrageStep
      rubrique={INTENTION_STEP.label}
      title={t('ProjectIntentStep.titre')}
      consigne={t('ProjectIntentStep.consigne')}
      pourquoi={t('ProjectIntentStep.pourquoi')}
      onNext={onNext}
      nextDisabled={value.length === 0}
      nextHint={t('ProjectIntentStep.indiceSuivant')}
    >
      {RAISON_CHOIX.map((option) => (
        <CadrageTile
          key={option.value}
          label={option.label}
          hint={option.hint}
          selected={value.includes(option.value)}
          onSelect={() => select(option.value)}
        />
      ))}
    </CadrageStep>
  );
}
