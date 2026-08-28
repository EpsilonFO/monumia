import { WORK_TYPES } from '@/constants/monument-options';
import type { WorkType } from '@/types';
import { CadrageStep, CadrageTile } from './CadrageStep';

interface ProjectTravauxStepProps {
  /**
   * `null` : la question n'a pas encore de réponse. `[]` : « Pas encore
   * déterminé » — une réponse à part entière, qui persiste une liste vide.
   */
  value: WorkType[] | null;
  onChange: (travaux: WorkType[] | null) => void;
  onNext: () => void;
  onBack?: () => void;
  /** Surtitre : « Nouveau projet » ou « Questionnaire » selon le parcours. */
  eyebrow: string;
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
 * « Pas encore déterminé » persiste une liste vide : le filtre redevient
 * fail-open et aucune aide n'est masquée faute de donnée.
 */
export function ProjectTravauxStep({
  value,
  onChange,
  onNext,
  onBack,
  eyebrow,
  saving,
}: ProjectTravauxStepProps) {
  const selected = value ?? [];
  const indetermine = value !== null && value.length === 0;

  const toggle = (type: WorkType) => {
    const next = selected.includes(type)
      ? selected.filter((t) => t !== type)
      : [...selected, type];
    // Tout décocher ramène à « sans réponse », pas à « pas encore déterminé » :
    // les deux se ressemblent mais seule la seconde est un choix explicite.
    onChange(next.length === 0 ? null : next);
  };

  return (
    <CadrageStep
      eyebrow={eyebrow}
      title="Sur quoi portent les travaux envisagés ?"
      intro="Plusieurs réponses possibles. Certaines aides ne financent qu'un type d'ouvrage précis."
      onNext={onNext}
      onBack={onBack}
      nextDisabled={value === null}
      nextHint="Cochez au moins un type de travaux, ou « Pas encore déterminé »."
      saving={saving}
    >
      <div
        role="group"
        aria-label="Types de travaux envisagés"
        className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3"
      >
        {WORK_TYPES.map((type) => (
          <CadrageTile
            key={type.value}
            label={type.label}
            multiple
            compact
            selected={selected.includes(type.value as WorkType)}
            onSelect={() => toggle(type.value as WorkType)}
          />
        ))}
      </div>

      <CadrageTile
        label="Pas encore déterminé"
        hint="Nous vous montrerons toutes les aides, sans filtrer sur le type de travaux."
        selected={indetermine}
        onSelect={() => onChange(indetermine ? null : [])}
      />
    </CadrageStep>
  );
}
