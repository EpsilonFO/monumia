import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { Loader2 } from 'lucide-react';
import { PlanLevier } from './FicheAvantDepot';
import { FicheQuestion } from './FicheQuestion';
import { Ico } from './Ico';
import { getEligibilityStatus } from '@/components/aide/eligibility-status';
import { questionsPourAide } from '@/lib/diagnostic-bilan';
import type {
  AideEvaluation,
  AideMatchResult,
  ProjectQuestionnaireAnswers,
  QcmQuestion,
} from '@/types';

const EN_LETTRES = ['', 'Une', 'Deux', 'Trois', 'Quatre', 'Cinq', 'Six', 'Sept', 'Huit', 'Neuf', 'Dix'];

interface Props {
  match: AideMatchResult;
  questions: QcmQuestion[];
  answers: ProjectQuestionnaireAnswers;
  /** Absent sans droit d'écriture sur le projet : les questions restent lisibles. */
  onRepondre?: (factKey: string, value: string | string[] | undefined) => void;
  envoiEnCours?: boolean;
  /** Le titre rédigé de chaque condition, et son résumé : un verdict se dit
   *  avec les mots de la fiche plutôt qu'avec le texte brut du règlement. */
  titres: Map<string, string>;
  resumes: Map<string, string>;
  dossierOuvert: boolean;
  ouverture: boolean;
  onDossier: () => void;
  lienAutres: string;
  /** Démarches affichées sous ce bloc (« Avant de déposer ») : le verdict y renvoie. */
  nbDemarches?: number;
}

type Etat = 'ok' | 'no' | 'info' | 'todo';

/**
 * « Êtes-vous éligible ? » : les questions que le moteur pose ENCORE pour cette
 * aide, et le verdict qui en sort. Le verdict est celui du moteur, relancé à
 * chaque réponse (cf. AideProjectPage) : rien n'est tranché ici.
 *
 * Une question répondue sort du QCM au diagnostic suivant. On la garde à
 * l'écran le temps de la visite, avec sa réponse, pour qu'une erreur de clic
 * se corrige sur place : c'est ce que fait la maquette.
 */
export function FicheEligibilite({
  match,
  questions,
  answers,
  onRepondre,
  envoiEnCours,
  titres,
  resumes,
  dossierOuvert,
  ouverture,
  onDossier,
  lienAutres,
  nbDemarches = 0,
}: Props) {
  const aideId = match.aide.id;
  const restantes = questionsPourAide(aideId, questions, answers);
  const [vues, setVues] = useState<QcmQuestion[]>(restantes);
  const cleRestantes = restantes.map((q) => q.id).join('|');
  useEffect(() => {
    setVues((deja) => {
      const connues = new Set(deja.map((q) => q.id));
      const nouvelles = restantes.filter((q) => !connues.has(q.id));
      return nouvelles.length ? [...deja, ...nouvelles] : deja;
    });
    // `restantes` se recalcule à chaque rendu : sa liste d'ids suffit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cleRestantes]);

  const statut = getEligibilityStatus(match);
  const evals: AideEvaluation[] = match.llmEvaluation?.evaluations ?? [];
  const libelle = (e: AideEvaluation) => (e.conditionId && titres.get(e.conditionId)) || e.critere;
  const idsPoses = new Set(restantes.map((q) => q.id));
  const remplies = evals.filter((e) => e.verdict === 'oui' || (e.verdict === 'incertitude' && e.clarified));
  const aConfirmer = evals.filter(
    (e) => e.verdict === 'incertitude' && !e.clarified && !(e.categorie && idsPoses.has(e.categorie)),
  );
  const refus = (match.criteresNonRemplis ?? []).map((t) => resumes.get(t) ?? t);
  const leviers = match.leviers ?? [];

  const etat: Etat =
    statut === 'eligible' ? 'ok' : statut === 'non-eligible' ? 'no' : statut === 'atteignable' ? 'info' : 'todo';
  const repondues = vues.length - restantes.length;
  const n = restantes.length;

  let titre: string;
  let aide: string;
  let pastille: string;
  if (etat === 'ok') {
    titre = 'Vous remplissez ces conditions.';
    aide = nbDemarches === 0
      ? 'Vérifiez les autres points dans le règlement complet.'
      : nbDemarches === 1
        ? 'Il reste un point à régler avant le dépôt, juste en dessous.'
        : `Il reste ${nbDemarches} points à régler avant le dépôt, juste en dessous.`;
    pastille = 'Éligible';
  } else if (etat === 'no') {
    titre = 'Cette aide ne correspond pas à votre projet.';
    aide = repondues > 0
      ? 'Vous pouvez changer une réponse si elle ne vous semble pas juste.'
      : 'Le motif vient de la fiche du monument ou de vos réponses au questionnaire.';
    pastille = 'Non éligible';
  } else if (etat === 'info') {
    titre = 'Une démarche vous sépare de cette aide.';
    aide = 'La condition manquante dépend d’une démarche que vous pouvez engager.';
    pastille = 'À débloquer';
  } else if (n > 0) {
    titre = repondues === 0
      ? `Êtes-vous éligible ? ${n <= 10 ? EN_LETTRES[n] : n} question${n > 1 ? 's' : ''} et vous saurez.`
      : n === 1 ? "Plus qu'une question." : `Encore ${n} questions.`;
    aide = aConfirmer.length
      ? 'Quelques points resteront à confirmer avec le financeur.'
      : 'Les autres conditions sont détaillées dans le règlement.';
    pastille = 'À vérifier';
  } else {
    titre = 'Il reste quelques points à confirmer avec le financeur.';
    aide = 'Rien dans vos réponses n’écarte cette aide.';
    pastille = 'À confirmer';
  }

  return (
    <div className={`elig${etat === 'todo' ? '' : ` ${etat}`}`} id="eligibilite">
      <div className="elig-head">
        <div>
          <h2>{titre}</h2>
          <p className="hint">{aide}</p>
        </div>
        <span className={`pill${etat === 'todo' ? '' : ` ${etat}`}`}><i />{pastille}</span>
      </div>

      {vues.length > 0 && (
        <div className="qs">
          {vues.map((q) => (
            <FicheQuestion
              key={q.id}
              question={q}
              value={answers[q.id] as string | string[] | undefined}
              onAnswer={onRepondre ? (v) => onRepondre(q.id, v) : undefined}
              disabled={envoiEnCours}
            />
          ))}
          {!onRepondre && n > 0 && (
            <p className="elig-foot">Seuls le chef de projet et son adjoint peuvent répondre à ces questions.</p>
          )}
        </div>
      )}

      {etat === 'info' && leviers.length > 0 && (
        <div className="qs">
          {leviers.map((l, i) => <PlanLevier key={i} levier={l} />)}
        </div>
      )}

      {etat !== 'no' && aConfirmer.length > 0 && (
        <div className="qs">
          {aConfirmer.map((e, i) => (
            <div key={i} className="q answered">
              <span className="q-ok">
                <span className="chip t-sand"><Ico nom="info" /></span>
                <p>{libelle(e)}<small>À confirmer avec le financeur au moment du dossier.</small></p>
              </span>
            </div>
          ))}
        </div>
      )}

      {remplies.length > 0 && (
        <details className="more">
          <summary>
            {remplies.length} condition{remplies.length > 1 ? 's' : ''} déjà remplie{remplies.length > 1 ? 's' : ''}
          </summary>
          <div className="qs">
            {remplies.map((e, i) => (
              <div key={i} className="q answered">
                <span className="q-ok">
                  <span className="chip t-green"><Ico nom="coche" /></span>
                  <p>{libelle(e)}</p>
                </span>
              </div>
            ))}
          </div>
        </details>
      )}

      {etat === 'ok' && (
        <div className="result" aria-live="polite">
          <p>
            {dossierOuvert ? 'Votre dossier est ouvert.' : 'Prochaine étape : réunir les pièces du dossier.'}
            <small>La décision finale revient au financeur.</small>
          </p>
          <button type="button" className="btn btn-main" onClick={onDossier} disabled={ouverture}>
            {ouverture && <Loader2 className="i animate-spin" />}
            {dossierOuvert ? 'Voir le dossier' : 'Commencer mon dossier'}
          </button>
        </div>
      )}
      {etat === 'no' && (
        <div className="result" aria-live="polite">
          <p>{refus[0] ?? 'Une condition de cette aide n’est pas remplie.'}</p>
          <Link className="btn btn-line" to={lienAutres}>Voir les autres aides</Link>
        </div>
      )}
    </div>
  );
}
