import { useTranslation } from 'react-i18next';
import { WORK_TYPES } from '@/constants/monument-options';
import { grouperReponses } from '@/lib/question-reponse';
import type { WorkType } from '@/types';
import { CadrageStep, CadrageTile } from './CadrageStep';
import { BlocsReponses } from './EcranQuestion';
import { TRAVAUX_STEP } from './etapes';

/** Les types de travaux sous leurs six intertitres (cf. `WORK_TYPES`). */
const BLOCS_TRAVAUX = grouperReponses(WORK_TYPES)?.blocs ?? [{ titre: null, options: [...WORK_TYPES] }];

interface ProjectTravauxStepProps {
  /**
   * `null` : la question n'a pas encore de réponse. `[]` : « Pas encore
   * déterminé » — une réponse à part entière, qui persiste une liste vide.
   */
  value: WorkType[] | null;
  onChange: (travaux: WorkType[] | null) => void;
  onNext: () => void;
  /** « Pas encore déterminé » : enregistre la liste vide et passe à la suite. */
  onIndetermine: () => void;
  onBack?: () => void;
  saving?: boolean;
}

/**
 * Écran « Sur quoi portent les travaux ? » du wizard projet.
 *
 * Alimente `projet.travaux_envisages`, que consomment les
 * `hard_filters.travaux` d'une trentaine d'aides : c'est ce qui écarte les
 * aides d'objet (orgues, mobilier, archives, parcs et jardins) d'un chantier de
 * toiture. La grille vivait auparavant en fin de formulaire monument, où elle
 * était systématiquement sautée — et le filtre étant fail-open, ces aides
 * ressortaient éligibles pour tout le monde. Le cadrage vit désormais sur le
 * PROJET : deux chantiers d'un même monument peuvent viser des ouvrages
 * différents, et n'ont donc pas les mêmes aides.
 *
 * « Pas encore déterminé », dans la barre du bas, persiste une liste vide : le
 * filtre redevient fail-open et aucune aide n'est masquée faute de donnée.
 */
export function ProjectTravauxStep({
  value,
  onChange,
  onNext,
  onIndetermine,
  onBack,
  saving,
}: ProjectTravauxStepProps) {
  const { t } = useTranslation('project');
  const selected = value ?? [];

  const toggle = (type: WorkType) => {
    const next = selected.includes(type)
      ? selected.filter((w) => w !== type)
      : [...selected, type];
    // Tout décocher ramène à « sans réponse », pas à « pas encore déterminé » :
    // les deux se ressemblent mais seule la seconde est un choix explicite.
    onChange(next.length === 0 ? null : next);
  };

  return (
    <CadrageStep
      rubrique={TRAVAUX_STEP.label}
      title={t('ProjectTravauxStep.titre')}
      consigne={t('consignes.plusieursReponses')}
      pourquoi={t('ProjectTravauxStep.pourquoi')}
      multiple
      onNext={onNext}
      onBack={onBack}
      // À la place du « Je ne sais pas, passer » des autres questions.
      onPasser={onIndetermine}
      libellePasser={t('ProjectTravauxStep.indetermine')}
      nextDisabled={value === null}
      nextHint={t('ProjectTravauxStep.indiceSuivant')}
      saving={saving}
      // « Tout refaire » depuis la page du projet repasse par cette étape.
      modifiablePlusTard
    >
      <BlocsReponses
        blocs={BLOCS_TRAVAUX.map((bloc) => ({
          titre: bloc.titre,
          cartes: bloc.options.map((type) => (
            <CadrageTile
              key={type.value}
              label={type.label}
              multiple
              selected={selected.includes(type.value as WorkType)}
              onSelect={() => toggle(type.value as WorkType)}
            />
          )),
        }))}
      />
    </CadrageStep>
  );
}
