import type { RepriseDurable } from '@/services/projet.service';
import { CadrageStep, CadrageTile } from './CadrageStep';
import { REPRISES_STEP } from './etapes';

interface ProjectReprisesStepProps {
  /** Les réponses proposées à la reprise, nommées par le serveur. */
  reprises: RepriseDurable[];
  /** `null` : pas encore répondu — « Continuer » reste inerte. */
  value: boolean | null;
  onChange: (reprendre: boolean | null) => void;
  onNext: () => void;
  onBack?: () => void;
  saving?: boolean;
}

/**
 * Écran « Reprendre vos réponses ? », posé avant le questionnaire d'un nouveau
 * projet quand le monument en porte déjà un autre.
 *
 * Les faits de scope `monument` et `proprietaire` ne changent pas d'un chantier
 * à l'autre (l'édifice est-il cultuel ? quel est le statut du porteur ?), et les
 * reposer à chaque projet est la première cause de questionnaire interminable au
 * second projet. Mais les reprendre EN SILENCE est pire : le questionnaire
 * démarre alors à la question 1 avec neuf réponses déjà décidées dans le dos de
 * l'utilisateur, et rien ne les lui montre — une réponse reprise n'étant plus
 * une incertitude, le moteur ne rend plus sa question et aucune fiche d'aide ne
 * l'offre à la correction.
 *
 * D'où cet écran : il MONTRE chaque réponse, question et valeur, et demande
 * l'accord. Un « non » repose simplement les questions ; rien n'est enregistré
 * avant la réponse, donc refuser ne laisse aucune trace.
 */
export function ProjectReprisesStep({
  reprises,
  value,
  onChange,
  onNext,
  onBack,
  saving,
}: ProjectReprisesStepProps) {
  const n = reprises.length;
  // Un seul projet source dans l'immense majorité des cas : on le nomme, c'est
  // ce qui permet de juger si la réponse est encore valable.
  const titres = [...new Set(reprises.map((r) => r.projetTitre).filter(Boolean))];
  const provenance =
    titres.length === 1 ? `de votre projet « ${titres[0]} »` : 'de vos autres projets';

  return (
    <CadrageStep
      rubrique={REPRISES_STEP.label}
      title="Reprendre vos réponses précédentes ?"
      pourquoi={`${n} réponse${n > 1 ? 's' : ''} ${provenance} décri${n > 1 ? 'vent' : 't'} le monument et son propriétaire, pas ce chantier-ci. Nous pouvons ${n > 1 ? 'les' : 'la'} reprendre pour vous éviter de répondre deux fois.`}
      avantReponses={
        <ul className="liste-reprises">
          {reprises.map((r) => (
            <li key={r.fact}>
              {r.question}{' '}
              {r.reponse ? (
                <b>{r.reponse}</b>
              ) : (
                // Les tranches d'un fait numérique sont fabriquées par le moteur
                // depuis les seuils des aides candidates : hors de ce contexte on
                // ne sait pas les nommer, et un libellé faux serait pire que rien.
                <em>(réponse déjà donnée)</em>
              )}
            </li>
          ))}
        </ul>
      }
      onNext={onNext}
      onBack={onBack}
      nextDisabled={value === null}
      nextHint="Dites-nous si nous reprenons ces réponses."
      saving={saving}
    >
      <CadrageTile
        label={`Oui, reprendre ${n > 1 ? 'ces réponses' : 'cette réponse'}`}
        hint={`Nous ne vous ${n > 1 ? 'les' : 'la'} reposerons pas. Vous pourrez toujours refaire tout le questionnaire depuis la page du projet.`}
        selected={value === true}
        onSelect={() => onChange(true)}
      />
      <CadrageTile
        label={`Non, me ${n > 1 ? 'les' : 'la'} reposer`}
        hint="Le questionnaire repartira de zéro sur ces points. Rien de votre autre projet n'est modifié."
        selected={value === false}
        onSelect={() => onChange(false)}
      />
    </CadrageStep>
  );
}
