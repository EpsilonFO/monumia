import {
  FAMILLE_OPTIONS,
  FAMILLE_TRAVAUX,
  FAMILLES_CHOIX,
  type Famille,
} from '@/constants/familles';
import { CadrageStep, CadrageTile } from './CadrageStep';
import { FAMILLES_STEP } from './etapes';

interface ProjectFamillesStepProps {
  /**
   * `null` : la question n'a pas encore de réponse. `[]` : « Je ne sais pas
   * encore, montrez-moi tout » — une réponse à part entière, qui persiste une
   * liste vide et ne filtre rien.
   */
  value: Famille[] | null;
  onChange: (familles: Famille[] | null) => void;
  onNext: () => void;
  onBack?: () => void;
  saving?: boolean;
}

const LIBELLES = new Map(FAMILLE_OPTIONS.map((o) => [o.value, o]));

/**
 * Écran « Que voulez-vous faire vivre ? » du wizard projet, posé juste après
 * l'intention « Faire vivre et ouvrir le lieu ».
 *
 * Alimente la clé réservée `_familles`, que le moteur croise avec
 * `Aide.familles` (`hors_famille`) : c'est ce qui écarte les aides d'un autre
 * thème d'un projet de spectacles — sans lui, monter un festival fait demander
 * si le projet est un hébergement touristique, si le musée a l'appellation
 * « Musée de France », quel est le budget de médiation.
 *
 * L'étape n'existe que pour cette intention : « Restaurer » et « Préparer le
 * projet » impliquent déjà leurs familles côté moteur (`FAMILLES_PAR_RAISON`)
 * et n'ont rien à demander.
 *
 * Deux tuiles à part, en pied d'écran :
 *
 * - « Des travaux sont nécessaires » ajoute `restauration_bati` ET rouvre
 *   l'étape des travaux, que cette intention saute par défaut. La moitié des
 *   projets « faire vivre » aménagent quelque chose.
 * - « Je ne sais pas encore, montrez-moi tout » persiste `[]` : rien n'est
 *   filtré. C'est le mode découverte, la moitié des usages annoncés — et il
 *   doit se choisir explicitement, pour qu'on sache ne plus reposer la
 *   question.
 */
export function ProjectFamillesStep({
  value,
  onChange,
  onNext,
  onBack,
  saving,
}: ProjectFamillesStepProps) {
  const selected = value ?? [];
  const toutMontrer = value !== null && value.length === 0;
  const avecTravaux = selected.includes(FAMILLE_TRAVAUX);

  const toggle = (famille: Famille) => {
    const next = selected.includes(famille)
      ? selected.filter((f) => f !== famille)
      : [...selected, famille];
    // Tout décocher ramène à « sans réponse », pas à « montrez-moi tout » :
    // les deux ne filtrent rien, mais seule la seconde est un choix.
    onChange(next.length === 0 ? null : next);
  };

  return (
    <CadrageStep
      rubrique={FAMILLES_STEP.label}
      title="Que voulez-vous faire vivre ?"
      consigne="Plusieurs réponses possibles."
      pourquoi="Les aides ne financent pas les mêmes activités, et nous ne vous poserons que les questions de celles que vous cochez."
      multiple
      onNext={onNext}
      onBack={onBack}
      nextDisabled={value === null}
      nextHint="Cochez au moins une activité, ou « Je ne sais pas encore »."
      saving={saving}
    >
      {FAMILLES_CHOIX.map((famille) => {
        const option = LIBELLES.get(famille);
        return (
          <CadrageTile
            key={famille}
            label={option?.label ?? famille}
            hint={option?.hint}
            multiple
            selected={selected.includes(famille)}
            onSelect={() => toggle(famille)}
          />
        );
      })}

      <CadrageTile
        label="Des travaux sont nécessaires"
        hint="Aménagement, mise aux normes, restauration : nous vous demanderons sur quoi ils portent."
        multiple
        selected={avecTravaux}
        onSelect={() => toggle(FAMILLE_TRAVAUX)}
      />

      <CadrageTile
        label="Je ne sais pas encore, montrez-moi tout"
        hint="Nous vous montrerons toutes les aides à portée du monument, sans filtrer sur l'activité."
        selected={toutMontrer}
        onSelect={() => onChange(toutMontrer ? null : [])}
      />
    </CadrageStep>
  );
}
