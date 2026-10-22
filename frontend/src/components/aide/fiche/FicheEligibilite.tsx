import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
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

// De deux à dix, le nombre de questions s'écrit en lettres (`FicheEligibilite.enLettres`) ;
// une seule question a sa propre phrase.
const EN_LETTRES = ['deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf', 'dix'] as const;

interface Props {
  match: AideMatchResult;
  questions: QcmQuestion[];
  answers: ProjectQuestionnaireAnswers;
  /** Les réponses sur lesquelles le diagnostic a été calculé (`qcmAnswers`).
   *  Entre un clic et le diagnostic suivant, `answers` a déjà la nouvelle
   *  réponse mais `match` et `questions` sont encore les anciens : croiser les
   *  deux faisait passer la question tout juste répondue dans les points « à
   *  confirmer avec le financeur ». Le décompte des questions se fait donc sur
   *  ces réponses-ci, et l'affichage des boutons sur `answers`. */
  answersDiagnostic?: ProjectQuestionnaireAnswers;
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
 *
 * Une fois éligible, le panneau se replie en douceur (`.elig-pli`, de 1fr à
 * 0fr) : il ne reste que son verdict et « Commencer mon dossier ». « Revoir mes
 * réponses » le rouvre, pour corriger un clic.
 */
export function FicheEligibilite({
  match,
  questions,
  answers,
  answersDiagnostic,
  onRepondre,
  envoiEnCours,
  titres,
  resumes,
  dossierOuvert,
  ouverture,
  onDossier,
  nbDemarches = 0,
}: Props) {
  const { t } = useTranslation('aide');
  const aideId = match.aide.id;
  const restantes = questionsPourAide(aideId, questions, answersDiagnostic ?? answers);
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
  const [deplie, setDeplie] = useState(false);
  const evals: AideEvaluation[] = match.llmEvaluation?.evaluations ?? [];
  const libelle = (e: AideEvaluation) => (e.conditionId && titres.get(e.conditionId)) || e.critere;
  // Une condition dont la question est à l'écran ne se répète pas en dessous,
  // qu'elle attende encore sa réponse ou qu'on vienne d'y répondre.
  const idsPoses = new Set([...vues, ...restantes].map((q) => q.id));
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
  const replie = etat === 'ok' && !deplie;

  let titre: string;
  let aide: string;
  let pastille: string;
  if (etat === 'ok') {
    titre = t('FicheEligibilite.ok.titre');
    aide = nbDemarches === 0
      ? t('FicheEligibilite.ok.aideReglement')
      : t('FicheEligibilite.ok.aidePoints', { count: nbDemarches });
    pastille = t('FicheEligibilite.pastille.eligible');
  } else if (etat === 'no') {
    titre = t('FicheEligibilite.no.titre');
    aide = repondues > 0 ? t('FicheEligibilite.no.aideRepondu') : t('FicheEligibilite.no.aide');
    pastille = t('FicheEligibilite.pastille.nonEligible');
  } else if (etat === 'info') {
    titre = t('FicheEligibilite.info.titre');
    aide = t('FicheEligibilite.info.aide');
    pastille = t('FicheEligibilite.pastille.aDebloquer');
  } else if (n > 0) {
    const nombre = n <= 10 && n >= 2 ? t(`FicheEligibilite.enLettres.${EN_LETTRES[n - 2]}`) : String(n);
    titre = repondues === 0
      ? t('FicheEligibilite.questions.titreDebut', { count: n, nombre })
      : n === 1 ? t('FicheEligibilite.questions.plusQuUne') : t('FicheEligibilite.questions.encore', { n });
    aide = aConfirmer.length
      ? t('FicheEligibilite.questions.aideAConfirmer')
      : t('FicheEligibilite.questions.aideReglement');
    pastille = t('FicheEligibilite.pastille.aVerifier');
  } else {
    titre = t('FicheEligibilite.reste.titre');
    aide = t('FicheEligibilite.reste.aide');
    pastille = t('FicheEligibilite.pastille.aConfirmer');
  }

  return (
    <div className={`elig${etat === 'todo' ? '' : ` ${etat}`}${replie ? ' replie' : ''}`} id="eligibilite" data-guide="aide.criteres">
      <div className="elig-head">
        <div>
          <h2>{titre}</h2>
          <div className="elig-pli">
            <div inert={replie}>
              <p className="hint">{aide}</p>
            </div>
          </div>
        </div>
        <span className={`pill${etat === 'todo' ? '' : ` ${etat}`}`}><i />{pastille}</span>
      </div>

      <div className="elig-pli">
        <div inert={replie}>

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
                <p className="elig-foot">{t('FicheEligibilite.lectureSeule')}</p>
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
                    <p>{libelle(e)}<small>{t('FicheEligibilite.aConfirmerFinanceur')}</small></p>
                  </span>
                </div>
              ))}
            </div>
          )}

          {remplies.length > 0 && (
            <details className="more">
              <summary>
                {t('FicheEligibilite.remplies', { count: remplies.length })}
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
        </div>
      </div>

      {etat === 'ok' && (
        <div className="result" aria-live="polite">
          {replie ? (
            <button type="button" className="revoir" onClick={() => setDeplie(true)}>
              {t('FicheEligibilite.revoir')}
            </button>
          ) : (
            <p>
              {dossierOuvert ? t('FicheEligibilite.dossierOuvert') : t('FicheEligibilite.prochaineEtape')}
              <small>
                {t('FicheEligibilite.decisionFinale')}{' '}
                <button type="button" className="revoir" onClick={() => setDeplie(false)}>
                  {t('FicheEligibilite.replier')}
                </button>
              </small>
            </p>
          )}
          <button
            type="button"
            className="btn btn-main"
            onClick={onDossier}
            disabled={ouverture}
            data-guide="aide.dossier"
          >
            {ouverture && <Loader2 className="i animate-spin" />}
            {dossierOuvert ? t('FicheEligibilite.voirDossier') : t('FicheEligibilite.commencer')}
          </button>
        </div>
      )}
      {etat === 'no' && (
        <div className="result" aria-live="polite">
          <p>{refus[0] ?? t('FicheEligibilite.conditionNonRemplie')}</p>
        </div>
      )}
    </div>
  );
}
