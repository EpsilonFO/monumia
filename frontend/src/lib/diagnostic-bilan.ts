import type {
  Aide,
  AideDiagnosticResult,
  AideMatchResult,
  DiagnosticInviteResult,
  ProjectQuestionnaireAnswers,
  QcmQuestion,
} from '@/types';
import i18n from '@/i18n';
import { getDisponibilite } from '@/components/aide/eligibility-status';
import { sanitizeQcmQuestions } from './qcm';

/**
 * Le bilan de fin de tronc commun : des chiffres CALCULÉS, jamais estimés.
 *
 * L'écran qui propose « découvrir maintenant » ou « continuer » ne vaut que
 * s'il dit vrai. Deux nombres à ne pas confondre, et c'est tout l'intérêt de
 * les séparer ici : ce que les RÉPONSES ont écarté (l'utilisateur y est pour
 * quelque chose) et ce que le monument met à portée (les filtres automatiques
 * ont déjà écarté le reste, sans qu'on ait rien demandé).
 */
export interface BilanDiagnostic {
  /** `totalAidesAnalysees` : les aides que le moteur a réellement examinées. */
  aPortee: number;
  eligibles: number;
  /** Parmi `eligibles`, celles dont la fenêtre de candidature est OUVERTE.
   *
   *  Séparé parce que la page projet range les autres sous « Disponibles
   *  bientôt » : annoncer « 1 aide mobilisable » puis n'en montrer aucune sous
   *  « Disponibles maintenant » se lit comme une panne. Les deux écrans lisent
   *  désormais le même `getDisponibilite`, et ne peuvent plus diverger. */
  eligiblesMaintenant: number;
  atteignables: number;
  aConfirmer: number;
  /** Refus IMPUTABLES aux réponses, pas aux filtres automatiques de la fiche. */
  ecarteesParReponses: number;
  /** Aides « à confirmer » qu'une seule question sépare encore d'un verdict. */
  aConfirmerUneQuestion: number;
  questionsRestantes: number;
  minutesEstimees: number;
}

/** Vingt secondes par question, arrondi aux cinq minutes, plancher à cinq. */
const SECONDES_PAR_QUESTION = 20;

export function minutesPourQuestions(questionsRestantes: number): number {
  if (questionsRestantes <= 0) return 0;
  const minutes = (questionsRestantes * SECONDES_PAR_QUESTION) / 60;
  return Math.max(5, Math.round(minutes / 5) * 5);
}

/**
 * Une question est RÉSOLUE quand elle porte au moins une réponse qui n'est ni
 * « passer » ni une échappatoire « je ne sais pas » : dans ces deux cas le fait
 * reste inconnu côté moteur, et la question a donc toujours quelque chose à
 * apporter à l'aide qu'elle sert.
 */
function estResolue(q: QcmQuestion, answers: ProjectQuestionnaireAnswers): boolean {
  const answer = answers[q.id];
  const given = (Array.isArray(answer) ? answer : [answer]).filter(
    (id): id is string => typeof id === 'string' && id !== 'skip',
  );
  if (given.length === 0) return false;
  const inconnues = new Set(q.options.filter((o) => o.unknown).map((o) => o.id));
  return given.some((id) => !inconnues.has(id));
}

/**
 * Questions du diagnostic qui portent ENCORE sur cette aide.
 *
 * Source de vérité : `q.aideIds`, jamais `evaluations[].categorie` — une
 * condition bloquée par une passerelle `applies_if` n'a pas de `categorie`
 * quand son propre fait est connu (cf. eligibility_engine.py). L'ordre est
 * celui du moteur, qui pose déjà les porteuses avant leurs dépendantes.
 */
export function questionsPourAide(
  aideId: string,
  questions: QcmQuestion[],
  answers: ProjectQuestionnaireAnswers,
): QcmQuestion[] {
  return questions.filter(
    (q) =>
      Array.isArray(q.aideIds) && q.aideIds.includes(aideId) && !estResolue(q, answers),
  );
}

/**
 * Le verdict d'une aide dans un diagnostic, pour sa fiche.
 *
 * Une aide écartée par sa question de périmètre ne figure dans aucun seau : le
 * moteur la traite comme une aide hors projet. Sa fiche perdait alors tout
 * verdict, et la réponse qui l'avait écartée ne se corrigeait plus. On rend à
 * la place un refus imputable à la réponse, motivé par la question elle-même.
 */
export function matchPourAide(
  diagnostic: AideDiagnosticResult,
  aide: Aide | null,
  aideId: string,
): AideMatchResult | null {
  const trouve = [
    ...diagnostic.aidesEligibles,
    ...(diagnostic.aidesAtteignables ?? []),
    ...diagnostic.aidesPotentiellementEligibles,
    ...diagnostic.aidesNonEligibles,
  ].find((m) => m.aide.id === aideId);
  if (trouve) return trouve;
  const question = diagnostic.aidesHorsPerimetre?.[aideId];
  if (question === undefined || !aide || aide.id !== aideId) return null;
  const motif = i18n.t('libAides:diagnosticBilan.horsPerimetre', { question });
  return {
    aide,
    statut: 'non_eligible',
    eligible: false,
    elimineParReponse: true,
    criteresRemplis: [],
    criteresNonRemplis: [motif],
    raisonIneligibilite: motif,
  };
}

export function bilanDiagnostic(result: AideDiagnosticResult): BilanDiagnostic {
  const questions = sanitizeQcmQuestions(result.qcmQuestions);
  const answers = result.qcmAnswers ?? {};
  const aConfirmer = result.aidesPotentiellementEligibles ?? [];
  const eligibles = result.aidesEligibles ?? [];
  const questionsRestantes = questions.length;
  return {
    aPortee: result.totalAidesAnalysees ?? 0,
    eligibles: eligibles.length,
    eligiblesMaintenant: eligibles.filter((m) => getDisponibilite(m) === 'maintenant').length,
    atteignables: (result.aidesAtteignables ?? []).length,
    aConfirmer: aConfirmer.length,
    // `elimineParReponse` distingue le refus dû à une réponse du refus dû aux
    // seuls filtres automatiques (territoire, protection, propriétaire) : seul
    // le premier est imputable au questionnaire qu'on vient de remplir.
    ecarteesParReponses: (result.aidesNonEligibles ?? []).filter((m) => m.elimineParReponse)
      .length,
    aConfirmerUneQuestion: aConfirmer.filter(
      (m) => questionsPourAide(m.aide.id, questions, answers).length === 1,
    ).length,
    questionsRestantes,
    minutesEstimees: minutesPourQuestions(questionsRestantes),
  };
}

/**
 * Bilan RÉDUIT du parcours invité : `DiagnosticInviteResult` n'a pas de seaux,
 * seulement une synthèse chiffrée et les questions restantes. On ne promet donc
 * à l'écran que ce qu'on sait — pas de « N aides écartées par vos réponses ».
 */
export function bilanInvite(
  result: DiagnosticInviteResult,
): Pick<BilanDiagnostic, 'questionsRestantes' | 'minutesEstimees'> {
  const questionsRestantes = sanitizeQcmQuestions(result.qcmQuestions).length;
  return { questionsRestantes, minutesEstimees: minutesPourQuestions(questionsRestantes) };
}
