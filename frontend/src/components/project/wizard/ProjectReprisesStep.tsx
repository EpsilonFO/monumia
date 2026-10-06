import type { RepriseDurable } from '@/services/projet.service';
import { CadrageStep } from './CadrageStep';
import { REPRISES_STEP } from './etapes';

interface ProjectReprisesStepProps {
  /** Les réponses proposées à la reprise, nommées par le serveur. */
  reprises: RepriseDurable[];
  /** Les clés cochées : celles qui seront reprises. */
  value: string[];
  onChange: (retenues: string[]) => void;
  onNext: () => void;
  onBack?: () => void;
  saving?: boolean;
}

/** Au-delà, chaque bloc se replie et n'annonce d'abord que son nombre de réponses. */
const REPLI_AU_DELA = 8;

const BLOCS: { scope: NonNullable<RepriseDurable['scope']>; titre: string }[] = [
  { scope: 'monument', titre: 'Le monument' },
  { scope: 'proprietaire', titre: 'Le porteur' },
];

/**
 * Écran « Reprendre vos réponses ? », posé avant le questionnaire quand
 * d'autres projets du monument ont déjà répondu à des questions durables.
 *
 * Les faits de scope `monument` et `proprietaire` ne changent pas d'un chantier
 * à l'autre (l'édifice est-il cultuel ? quel est le statut du porteur ?), et les
 * reposer à chaque projet est la première cause de questionnaire interminable au
 * second projet. Mais les reprendre EN SILENCE est pire : le questionnaire
 * démarre alors à la question 1 avec neuf réponses déjà décidées dans le dos de
 * l'utilisateur, et rien ne les lui montre. Une réponse reprise n'étant plus
 * une incertitude, le moteur ne rend plus sa question et aucune fiche d'aide ne
 * l'offre à la correction.
 *
 * D'où cet écran : il MONTRE chaque réponse, rangée sous « Le monument » ou
 * « Le porteur », et la reprise se décide réponse par réponse. Tout est coché
 * par défaut ; une case décochée repose sa question. Rien n'est enregistré
 * avant « Continuer ».
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
  const cochees = new Set(value);
  // Un seul projet source dans l'immense majorité des cas : on le nomme, c'est
  // ce qui permet de juger si la réponse est encore valable.
  const titres = [...new Set(reprises.map((r) => r.projetTitre).filter(Boolean))];
  const provenance =
    titres.length === 1 ? `de votre projet « ${titres[0]} »` : 'de vos autres projets';
  const replier = n > REPLI_AU_DELA;
  // Une reprise sans scope (serveur d'avant le champ) tombe avec le monument.
  const blocs = BLOCS.map((b) => ({
    ...b,
    lignes: reprises.filter((r) => (r.scope ?? 'monument') === b.scope),
  })).filter((b) => b.lignes.length > 0);

  const basculer = (fact: string) =>
    onChange(cochees.has(fact) ? value.filter((f) => f !== fact) : [...value, fact]);
  const toutDecoche = value.length === 0;

  const nb = value.length;
  const consigne = toutDecoche
    ? 'Aucune réponse reprise : toutes ces questions vous seront reposées.'
    : `${nb} réponse${nb > 1 ? 's' : ''} sur ${n} ser${nb > 1 ? 'ont' : 'a'} reprise${nb > 1 ? 's' : ''}. Décochez celles à vous faire reposer.`;

  return (
    <CadrageStep
      rubrique={REPRISES_STEP.label}
      title="Reprendre vos réponses précédentes ?"
      consigne={consigne}
      pourquoi={`${n} réponse${n > 1 ? 's' : ''} ${provenance} décri${n > 1 ? 'vent' : 't'} le monument et son porteur, pas ce chantier-ci. Nous pouvons ${n > 1 ? 'les' : 'la'} reprendre pour vous éviter de répondre deux fois. Vous pourrez toujours refaire tout le questionnaire depuis la page du projet.`}
      avantReponses={
        <button
          type="button"
          className="reprises-tout"
          onClick={() => onChange(toutDecoche ? reprises.map((r) => r.fact) : [])}
        >
          {toutDecoche ? 'Tout cocher' : 'Tout décocher'}
        </button>
      }
      multiple
      onNext={onNext}
      onBack={onBack}
      saving={saving}
    >
      {blocs.map((bloc) => {
        const lignes = (
          <ul className="reprises-lignes">
            {bloc.lignes.map((r) => (
              <li key={r.fact}>
                <label>
                  <input
                    type="checkbox"
                    checked={cochees.has(r.fact)}
                    onChange={() => basculer(r.fact)}
                  />
                  <span className="q" title={r.question}>
                    {r.question}
                  </span>
                  {r.reponse ? (
                    <span className="tag">{r.reponse}</span>
                  ) : (
                    // Les tranches d'un fait numérique sont fabriquées par le
                    // moteur depuis les seuils des aides candidates : hors de ce
                    // contexte on ne sait pas toujours les nommer, et un libellé
                    // faux serait pire que rien.
                    <span className="tag vide">réponse déjà donnée</span>
                  )}
                </label>
              </li>
            ))}
          </ul>
        );
        const retenuesBloc = bloc.lignes.filter((r) => cochees.has(r.fact)).length;
        const compte = `${retenuesBloc} sur ${bloc.lignes.length} reprise${retenuesBloc > 1 ? 's' : ''}`;
        return (
          <div className="grp" key={bloc.scope}>
            {replier ? (
              <details>
                <summary className="grp-t">
                  {bloc.titre} · {compte}
                </summary>
                {lignes}
              </details>
            ) : (
              <>
                <p className="grp-t">
                  {bloc.titre} · {compte}
                </p>
                {lignes}
              </>
            )}
          </div>
        );
      })}
    </CadrageStep>
  );
}
