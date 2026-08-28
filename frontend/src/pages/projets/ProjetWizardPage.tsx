import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router';
import { ArrowRight, Loader2 } from 'lucide-react';
import { ProjectQuestionnaire } from '@/components/project/ProjectQuestionnaire';
import { ProjectIntentStep } from '@/components/project/wizard/ProjectIntentStep';
import { ProjectTravauxStep } from '@/components/project/wizard/ProjectTravauxStep';
import { PerilStep } from '@/components/project/wizard/PerilStep';
import { WizardShell } from '@/components/project/wizard/WizardShell';
import { DiagnosticLoader } from '@/components/project/wizard/DiagnosticLoader';
import {
  PERIL_RATTRAPAGE_STEP,
  PROJET_WIZARD_STEPS,
  type WizardProgress,
  type WizardStepKey,
} from '@/components/project/wizard/WizardRail';
import { AllClear } from '@/components/illustrations';
import { IconAttention, IconRafraichir } from '@/components/icons';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useProjetStore } from '@/stores/useProjetStore';
import { useAideStore } from '@/stores/useAideStore';
import { monumentService } from '@/services/monument.service';
import { projetService } from '@/services/projet.service';
import { aideService } from '@/services/aide.service';
import { sanitizeQcmQuestions } from '@/lib/qcm';
import { RAISONS_KEY, readRaisons } from '@/constants/raisons';
import type { EtatConservation } from '@/constants/monument-options';
import { ROUTES } from '@/constants/routes';
import { C, SERIF } from '@/lib/brand';
import { toast } from 'sonner';
import type {
  Monument,
  ProjectQuestionnaireAnswers,
  QcmQuestion,
  WorkType,
} from '@/types';

/**
 * Création (ou reprise) d'un PROJET de travaux sur un monument déjà décrit.
 *
 * Le monument vient de l'URL ; on ne redemande donc ni son identification ni sa
 * protection. Le parcours part directement de l'intention (« Que voulez-vous
 * faire ? »), puis des travaux, puis du questionnaire.
 *
 * Deux entrées :
 *  - sans paramètre : nouveau projet, créé par POST à la fin de l'étape travaux ;
 *  - `?projet=<id>` : « Refaire le questionnaire » d'un projet existant —
 *    intentions et travaux préremplis, PATCH au lieu de POST.
 *
 * Rattrapage : si le monument n'a jamais répondu à la question du péril (fiche
 * créée avant qu'elle n'existe), un écran la pose en préambule. Sans lui, elle
 * ne serait plus jamais posée — le wizard monument ne repasse pas.
 */
export function ProjetWizardPage() {
  const navigate = useNavigate();
  const { monumentId } = useParams();
  const [searchParams] = useSearchParams();
  const existingProjetId = searchParams.get('projet');

  const upsertProjet = useProjetStore((s) => s.upsertProjet);
  const updateMonument = useMonumentStore((s) => s.updateMonument);
  const setDiagnostic = useAideStore((s) => s.setDiagnostic);

  const [monument, setMonument] = useState<Monument | null>(null);
  const [projetId, setProjetId] = useState<string | null>(existingProjetId);
  const [saving, setSaving] = useState(false);
  const [answers, setAnswers] = useState<ProjectQuestionnaireAnswers>({});
  // Intentions de l'étape « Votre projet » (finalités du catalogue). Elles
  // préfiltrent les aides candidates AVANT la génération du questionnaire.
  const [raisons, setRaisons] = useState<string[]>([]);
  // `travaux === null` : pas de réponse ; `[]` : « Pas encore déterminé ».
  const [travaux, setTravaux] = useState<WorkType[] | null>(null);
  // Rattrapage du péril : `null` tant qu'on ne sait pas si la question a déjà
  // été posée (fiche en cours de chargement) ou qu'elle ne l'a jamais été.
  const [etatConservation, setEtatConservation] = useState<EtatConservation | null>(null);
  const [besoinPeril, setBesoinPeril] = useState(false);
  const [step, setStep] = useState<WizardStepKey>('intention');
  const [progress, setProgress] = useState<WizardProgress | null>(null);
  // Questionnaire du moteur d'aides : on lance un premier diagnostic déterministe
  // (intentions seules, sans réponses) dès l'étape 3 pour obtenir les questions à
  // poser (faits manquants) et le résultat de base.
  const [questions, setQuestions] = useState<QcmQuestion[]>([]);
  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [loadedCadrageKey, setLoadedCadrageKey] = useState<string | null>(null);

  // Le questionnaire dépend du cadrage du PROJET : les intentions filtrent les
  // aides candidates, les travaux en font tomber par hard_filter. Le péril n'y
  // figure plus — il appartient au monument et ne change pas d'un projet à
  // l'autre. Revenir en arrière et changer l'un des deux régénère.
  const cadrageKey = [
    raisons.join('|'),
    travaux === null ? '?' : travaux.join('|'),
  ].join('#');

  const steps = useMemo(
    () => (besoinPeril ? [PERIL_RATTRAPAGE_STEP, ...PROJET_WIZARD_STEPS] : PROJET_WIZARD_STEPS),
    [besoinPeril],
  );

  const eyebrow = existingProjetId ? 'Questionnaire' : 'Nouveau projet';

  // Hors AppLayout, les stores peuvent être vides (arrivée directe par URL) :
  // on charge la fiche pour la mini-fiche du rail et le rattrapage du péril.
  useEffect(() => {
    if (!monumentId) return;
    monumentService
      .getById(monumentId)
      .then((m) => {
        setMonument(m);
        if (m.etatConservation) {
          setEtatConservation(m.etatConservation);
        } else {
          setBesoinPeril(true);
          setStep('peril');
        }
      })
      .catch(() => {
        // Non bloquant : le rail affiche simplement moins de contexte.
      });
  }, [monumentId]);

  // « Refaire le questionnaire » : on reprend le cadrage du projet existant.
  const prefilled = useRef(false);
  useEffect(() => {
    if (!existingProjetId) return;
    projetService
      .getById(existingProjetId)
      .then((p) => {
        // Préremplissage unique : ne jamais écraser ce que l'utilisateur vient
        // de cocher si le projet arrive en retard.
        if (prefilled.current) return;
        prefilled.current = true;
        const previous = readRaisons(p.questionnaire);
        if (previous.length > 0) setRaisons(previous);
        setTravaux(p.travauxEnvisages);
      })
      .catch(() => {
        toast.error('Ce projet est introuvable.');
      });
  }, [existingProjetId]);

  // Dès l'entrée dans le questionnaire, on calcule le diagnostic déterministe de
  // base (intentions seules, sans réponses) pour en déduire les questions à
  // poser — les faits manquants qui bloquent le plus d'aides, restreints aux
  // aides qui servent le projet déclaré. Le moteur étant pur et rapide, c'est
  // immédiat.
  useEffect(() => {
    if (step !== 'questionnaire' || !projetId || loadedCadrageKey === cadrageKey || loadError) {
      return;
    }
    let cancelled = false;
    setLoadingQuestions(true);
    aideService
      .runDeterministicDiagnostic(projetId, { [RAISONS_KEY]: raisons })
      .then((result) => {
        if (cancelled) return;
        setQuestions(sanitizeQcmQuestions(result.qcmQuestions));
        setLoadedCadrageKey(cadrageKey);
      })
      .catch((err) => {
        console.error('Erreur diagnostic déterministe:', err);
        if (!cancelled) setLoadError(true);
      })
      .finally(() => {
        if (!cancelled) setLoadingQuestions(false);
      });
    return () => {
      cancelled = true;
    };
  }, [step, projetId, raisons, cadrageKey, loadedCadrageKey, loadError]);

  // Rattrapage du péril : la réponse va sur le MONUMENT (elle décrit le bien).
  const handlePerilNext = async () => {
    if (!monumentId || etatConservation === null) return;
    setSaving(true);
    try {
      const updated = await monumentService.update(monumentId, {
        etatConservation,
      });
      setMonument(updated);
      updateMonument(monumentId, updated);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Erreur lors de l’enregistrement de l’état du monument"
      );
      return;
    } finally {
      setSaving(false);
    }
    setStep('intention');
  };

  // Fin de l'étape travaux : le cadrage vit sur le PROJET, que le moteur relit
  // côté serveur pour ses hard_filters — on le persiste donc AVANT de générer
  // le questionnaire. En cas d'échec on reste sur l'écran : partir avec des
  // travaux non enregistrés donnerait un diagnostic calculé sur l'état
  // précédent, sans que rien ne le signale.
  const handleTravauxNext = async () => {
    if (!monumentId || travaux === null) return;
    setSaving(true);
    try {
      const projet = projetId
        ? await projetService.update(projetId, { travauxEnvisages: travaux })
        : await projetService.create(monumentId, { travauxEnvisages: travaux });
      upsertProjet(projet);
      setProjetId(projet.id);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Erreur lors de l’enregistrement de votre projet"
      );
      return;
    } finally {
      setSaving(false);
    }
    // Changer le cadrage périme les réponses déjà données (leurs questions
    // peuvent disparaître) — on repart d'un questionnaire propre.
    if (loadedCadrageKey !== null && loadedCadrageKey !== cadrageKey) {
      setAnswers({});
      setQuestions([]);
    }
    setStep('questionnaire');
  };

  // Questionnaire → page du projet : on persiste réponses ET intentions sur le
  // projet (la page recalcule le même diagnostic à partir de là), puis on amorce
  // le store pour éviter un écran vide.
  const handleQuestionnaireNext = async () => {
    if (!projetId) return;
    const questionnaire: ProjectQuestionnaireAnswers = { ...answers, [RAISONS_KEY]: raisons };
    setSaving(true);
    setStep('diagnostic');
    try {
      upsertProjet(await projetService.update(projetId, { questionnaire }));
    } catch (err) {
      console.error('Erreur enregistrement questionnaire (ignorée):', err);
    }
    try {
      setDiagnostic(projetId, await aideService.runProjectDiagnostic(projetId, questionnaire));
    } catch (err) {
      console.error('Erreur diagnostic:', err);
    }
    // Leave `saving` true through the navigation — the component unmounts.
    navigate(ROUTES.PROJET_DETAIL(projetId));
  };

  // Quitter : le projet n'est créé qu'à la fin de l'étape travaux, et les
  // réponses au questionnaire ne sont écrites qu'à la toute fin.
  const exitTo = projetId
    ? ROUTES.PROJET_DETAIL(projetId)
    : monumentId
      ? `${ROUTES.MONUMENT_DETAIL(monumentId)}?tab=projets`
      : ROUTES.MONUMENTS;

  return (
    <WizardShell
      steps={steps}
      step={step}
      monument={monument}
      progress={step === 'questionnaire' ? progress : null}
      confirmQuit={step === 'questionnaire' && Object.keys(answers).length > 0}
      quitDisabled={step === 'diagnostic'}
      exitTo={exitTo}
    >
      {step === 'peril' && (
        <PerilStep
          eyebrow={eyebrow}
          value={etatConservation}
          onChange={setEtatConservation}
          onNext={handlePerilNext}
          saving={saving}
        />
      )}

      {step === 'intention' && (
        <ProjectIntentStep
          value={raisons}
          onChange={setRaisons}
          onNext={() => setStep('travaux')}
          retake={!!existingProjetId}
        />
      )}

      {step === 'travaux' && (
        <ProjectTravauxStep
          eyebrow={eyebrow}
          value={travaux}
          onChange={setTravaux}
          onNext={handleTravauxNext}
          onBack={() => setStep('intention')}
          saving={saving}
        />
      )}

      {step === 'questionnaire' && (
        <div className="space-y-5">
          {/* Pendant le questionnaire lui-même, pas d'en-tête : la question est
              la vedette et tout doit tenir à l'écran — le rail situe déjà
              l'étape. L'en-tête ne sert que les états d'attente/erreur/vide. */}
          {(loadingQuestions || loadError || questions.length === 0) && (
            <div className="space-y-1.5">
              <div
                className="text-[12px] font-semibold uppercase tracking-[0.2em]"
                style={{ color: C.orange }}
              >
                {eyebrow}
              </div>
              <h1
                className="text-[clamp(1.4rem,3vw,1.8rem)] leading-tight"
                style={{ fontFamily: SERIF, color: C.ink }}
              >
                Précisons votre projet
              </h1>
              <p className="max-w-lg text-[14px] leading-relaxed" style={{ color: C.grayFg }}>
                Vos réponses affinent la liste des aides. Répondez librement&nbsp;—
                passer une question est tout à fait valable.
              </p>
            </div>
          )}

          {loadingQuestions ? (
            <div
              className="flex items-center gap-3 py-10 text-[14px]"
              style={{ color: C.grayMuted }}
            >
              <Loader2 className="h-4 w-4 animate-spin" style={{ color: C.blueLight }} />
              Analyse de votre monument…
            </div>
          ) : loadError ? (
            <div
              className="flex flex-col items-start gap-4 rounded-2xl border p-6"
              style={{ borderColor: C.border, background: C.card }}
            >
              <span
                className="flex h-11 w-11 items-center justify-center rounded-xl"
                style={{ background: 'var(--destructive-muted)', color: 'var(--destructive)' }}
              >
                <IconAttention className="h-5 w-5" />
              </span>
              <div>
                <p className="text-[15px] font-semibold" style={{ color: C.ink }}>
                  Le questionnaire n&rsquo;a pas pu être chargé.
                </p>
                <p className="mt-1 text-[14px]" style={{ color: C.grayFg }}>
                  Vérifiez votre connexion puis réessayez&nbsp;— votre projet est bien
                  enregistré.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setLoadError(false)}
                className="inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-[14px] font-semibold text-white transition-all hover:shadow-[var(--shadow-pop)]"
                style={{ background: C.orange }}
              >
                <IconRafraichir className="h-4 w-4" />
                Réessayer
              </button>
            </div>
          ) : questions.length === 0 ? (
            <div className="flex flex-col items-center gap-5 py-8 text-center">
              <AllClear />
              <p
                className="max-w-md text-[15px] leading-relaxed"
                style={{ color: C.grayFg }}
              >
                Aucune précision supplémentaire n&rsquo;est nécessaire pour ce projet.
                Lancez le diagnostic pour découvrir les aides mobilisables.
              </p>
              <button
                type="button"
                disabled={saving}
                onClick={handleQuestionnaireNext}
                className="group inline-flex items-center gap-2 rounded-2xl px-7 py-3.5 text-[16px] font-semibold text-white transition-all hover:shadow-[var(--shadow-pop)] disabled:opacity-60"
                style={{ background: C.orange }}
              >
                Voir les aides
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </button>
            </div>
          ) : (
            <ProjectQuestionnaire
              questions={questions}
              value={answers}
              onChange={setAnswers}
              onComplete={handleQuestionnaireNext}
              submitting={saving}
              onProgress={setProgress}
            />
          )}
        </div>
      )}

      {step === 'diagnostic' && <DiagnosticLoader />}
    </WizardShell>
  );
}
