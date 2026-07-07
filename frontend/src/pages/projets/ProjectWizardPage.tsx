import { useEffect, useState } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router';
import { ArrowRight, Loader2 } from 'lucide-react';
import { MerimeeSearch } from '@/components/monument/MerimeeSearch';
import { MonumentForm } from '@/components/monument/MonumentForm';
import { ProjectQuestionnaire } from '@/components/project/ProjectQuestionnaire';
import { WizardShell } from '@/components/project/wizard/WizardShell';
import { DiagnosticLoader } from '@/components/project/wizard/DiagnosticLoader';
import type { WizardProgress, WizardStepKey } from '@/components/project/wizard/WizardRail';
import { AllClear } from '@/components/illustrations';
import { IconAttention, IconRafraichir } from '@/components/icons';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useAideStore } from '@/stores/useAideStore';
import { monumentService } from '@/services/monument.service';
import { merimeeService } from '@/services/merimee.service';
import { aideService } from '@/services/aide.service';
import { sanitizeQcmQuestions } from '@/lib/qcm';
import { REGIONS } from '@/constants/regions';
import { MATERIAUX, TYPES_COUVERTURE } from '@/constants/monument-options';
import { ROUTES } from '@/constants/routes';
import { C, SERIF } from '@/lib/brand';
import { toast } from 'sonner';
import type {
  AideDiagnosticResult,
  MerimeeRecord,
  Monument,
  ProjectQuestionnaireAnswers,
  ProtectionLevel,
  QcmQuestion,
  Region,
} from '@/types';

const REGION_LABEL_TO_VALUE: Record<string, string> = Object.fromEntries(
  REGIONS.map((r) => [r.label.toLowerCase(), r.value])
);

export function ProjectWizardPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // « Refaire le questionnaire » d'un projet existant : on rejoue directement
  // l'étape 2 du wizard pour ce monument (questionnaire vierge), sans repasser
  // par la création de la fiche.
  const existingMonumentId = searchParams.get('monument');
  const user = useAuthStore((s) => s.user);
  const addMonument = useMonumentStore((s) => s.addMonument);
  const setActiveMonument = useMonumentStore((s) => s.setActiveMonument);
  const setDiagnostic = useAideStore((s) => s.setDiagnostic);

  const [step, setStep] = useState<WizardStepKey>(existingMonumentId ? 2 : 1);
  const [mode, setMode] = useState<'search' | 'manual'>('search');
  const [prefillData, setPrefillData] = useState<Partial<Monument> | null>(null);
  const [saving, setSaving] = useState(false);
  const [monumentId, setMonumentId] = useState<string | null>(existingMonumentId);
  const [monument, setMonument] = useState<Monument | null>(null);
  const [answers, setAnswers] = useState<ProjectQuestionnaireAnswers>({});
  const [progress, setProgress] = useState<WizardProgress | null>(null);
  // Questionnaire du moteur d'aides : on lance un premier diagnostic déterministe
  // (sans réponses) dès l'étape 2 pour obtenir les questions à poser (faits
  // manquants) et le résultat de base. Les réponses ne sont jamais renvoyées au
  // moteur : elles se résolvent côté client via eliminationsParOption.
  const [questions, setQuestions] = useState<QcmQuestion[]>([]);
  const [baseResult, setBaseResult] = useState<AideDiagnosticResult | null>(null);
  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const [loadError, setLoadError] = useState(false);

  // Hors AppLayout, le store peut être vide (arrivée directe ?monument=id) :
  // on charge la fiche pour la mini-fiche du rail.
  useEffect(() => {
    if (!existingMonumentId) return;
    monumentService
      .getById(existingMonumentId)
      .then(setMonument)
      .catch(() => {
        // Non bloquant : le rail affiche simplement moins de contexte.
      });
  }, [existingMonumentId]);

  const handleMerimeeSelect = async (searchRecord: MerimeeRecord) => {
    try {
      const fullRecord = await merimeeService.getByReference(searchRecord.reference);
      const record = fullRecord ?? searchRecord;
      const lastOf = (s: string | undefined) => s?.split(';').pop()?.trim() ?? '';

      const typoEntries = (record.typologie_de_la_protection ?? '')
        .split(';')
        .map((s) => s.toLowerCase().trim());
      let protection: ProtectionLevel = 'non_protege';
      for (const t of typoEntries) {
        if (t.includes('classé')) protection = 'classe';
        else if (t.includes('inscrit')) protection = 'inscrit';
      }

      const regionValue = REGION_LABEL_TO_VALUE[record.region?.toLowerCase() ?? ''] ?? '';
      const titre = record.titre_editorial_de_la_notice ?? '';

      const PROPRIETAIRE_MAP: Record<string, Monument['proprietaire']> = {
        commune: 'public_commune',
        communal: 'public_commune',
        'département': 'public_departement',
        departemental: 'public_departement',
        'région': 'public_region',
        regional: 'public_region',
        'état': 'public_etat',
        etat: 'public_etat',
        'propriété privée': 'prive_personne_physique',
        'privé': 'prive_personne_physique',
        prive: 'prive_personne_physique',
        sci: 'prive_sci',
        association: 'association',
        mixte: 'mixte',
      };
      const statutRaw = record.statut_juridique_de_l_edifice?.toLowerCase().trim() ?? '';
      const proprietaireGuess =
        PROPRIETAIRE_MAP[statutRaw] ??
        Object.entries(PROPRIETAIRE_MAP).find(([k]) => statutRaw.includes(k))?.[1] ??
        undefined;

      const materiauxRaw = lastOf(
        record.materiaux_de_la_couverture || record.materiaux_du_gros_oeuvre
      ).toLowerCase();
      const materiaux = materiauxRaw
        ? MATERIAUX.filter((m) => materiauxRaw.includes(m.value)).map((m) => m.value)
        : undefined;

      const couvertureRaw = lastOf(record.type_de_couverture).toLowerCase();
      const typeCouverture =
        TYPES_COUVERTURE.find((t) => couvertureRaw.includes(t.value))?.value || undefined;

      let dateProtection: string | undefined;
      const lastDateEntry = lastOf(record.date_et_typologie_de_la_protection);
      if (lastDateEntry) {
        const datePart = lastDateEntry.split(':')[0]?.trim() ?? '';
        if (/^\d{4}\/\d{2}\/\d{2}$/.test(datePart)) {
          dateProtection = datePart.replace(/\//g, '-');
        }
      }
      const typeProtection =
        lastOf(record.date_et_typologie_de_la_protection) ||
        lastOf(record.typologie_de_la_protection) ||
        undefined;

      setPrefillData({
        nom: titre,
        referenceMerimee: record.reference,
        commune: record.commune_actuelle || record.commune_forme_index,
        codeInsee: record.cog_insee_lors_de_la_protection || undefined,
        departement: record.departement_en_lettres,
        region: regionValue as Region,
        protection,
        dateProtection,
        typeProtection,
        siecleConstruction:
          record.format_abrege_du_siecle_de_construction ||
          record.siecle_de_la_campagne_principale_de_construction ||
          undefined,
        typeCouverture,
        materiaux: materiaux?.length ? materiaux : undefined,
        proprietaire: proprietaireGuess,
        descriptionGenerale: record.precision_de_la_protection || undefined,
      });
      setMode('manual');
    } catch (err) {
      toast.error(
        err instanceof Error
          ? err.message
          : 'Erreur lors de la récupération de la fiche Mérimée'
      );
    }
  };

  const handleFormSubmit = async (data: Partial<Monument>) => {
    if (!user) return;
    setSaving(true);
    try {
      const monument = await monumentService.create({
        nom: data.nom ?? 'Mon monument',
        commune: data.commune ?? '',
        codeInsee: data.codeInsee ?? '',
        protection: data.protection ?? 'non_protege',
        proprietaire:
          data.proprietaire ??
          (user.segment === 'commune' ? 'public_commune' : 'prive_personne_physique'),
        etatConservation: data.etatConservation ?? 'moyen',
        referenceMerimee: data.referenceMerimee,
        dateProtection: data.dateProtection,
        typeProtection: data.typeProtection,
        affectataire: data.affectataire,
        siecleConstruction: data.siecleConstruction,
        periodeConstruction: data.periodeConstruction,
        superficie: data.superficie,
        materiaux: data.materiaux,
        typeCouverture: data.typeCouverture,
        nombreNiveaux: data.nombreNiveaux,
        descriptionGenerale: data.descriptionGenerale,
        travauxEnvisages: data.travauxEnvisages,
        urgenceTravaux: data.urgenceTravaux,
        diagnosticRealise: data.diagnosticRealise,
        derniersTravaux: data.derniersTravaux,
        descriptionEtat: data.descriptionEtat,
      });

      addMonument(monument);
      setActiveMonument(monument.id);
      setMonumentId(monument.id);
      setMonument(monument);
      setStep(2);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Erreur lors de la création du monument'
      );
    } finally {
      setSaving(false);
    }
  };

  // Dès l'entrée à l'étape 2, on calcule le diagnostic déterministe de base
  // (sans réponses) pour en déduire les questions à poser — les faits manquants
  // qui bloquent le plus d'aides. Le moteur étant pur et rapide, c'est immédiat.
  useEffect(() => {
    if (step !== 2 || !monumentId || baseResult || loadError) return;
    let cancelled = false;
    setLoadingQuestions(true);
    aideService
      .runDeterministicDiagnostic(monumentId, {})
      .then((result) => {
        if (cancelled) return;
        setBaseResult(result);
        setQuestions(sanitizeQcmQuestions(result.qcmQuestions));
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
  }, [step, monumentId, baseResult, loadError]);

  // Étape 2 → projet : on persiste les réponses sur le monument (la page projet
  // recalcule le même diagnostic à partir de là), on résout le QCM côté client
  // (eliminationsParOption) et on amorce le store pour éviter un écran vide.
  const handleQuestionnaireNext = async () => {
    if (!monumentId) return;
    setSaving(true);
    setStep(3);
    try {
      await monumentService.update(monumentId, { questionnaire: answers });
    } catch (err) {
      // Column may not exist yet (pre-migration) — degrade gracefully.
      console.error('Erreur enregistrement questionnaire (ignorée):', err);
    }
    try {
      setDiagnostic(monumentId, await aideService.runProjectDiagnostic(monumentId, answers));
    } catch (err) {
      console.error('Erreur diagnostic:', err);
    }
    // Leave `saving` true through the navigation — the component unmounts.
    navigate(ROUTES.PROJET_DETAIL(monumentId));
  };

  // Le wizard vit hors AppLayout : on réintroduit son garde de segment.
  if (user && user.segment === 'btp') {
    return <Navigate to="/btp" replace />;
  }

  const exitTo = existingMonumentId
    ? ROUTES.PROJET_DETAIL(existingMonumentId)
    : ROUTES.PROJETS;
  const confirmQuit = step === 2 && Object.keys(answers).length > 0;

  return (
    <WizardShell
      step={step}
      monument={monument}
      progress={step === 2 ? progress : null}
      confirmQuit={confirmQuit}
      exitTo={exitTo}
    >
      {step === 1 && (
        <div className="space-y-4">
          <div className="space-y-1.5">
            <div
              className="text-[12px] font-semibold uppercase tracking-[0.2em]"
              style={{ color: C.orange }}
            >
              Nouveau projet
            </div>
            <h1
              className="text-[clamp(1.5rem,3.2vw,2rem)] leading-tight"
              style={{ fontFamily: SERIF, color: C.ink }}
            >
              Commençons par votre monument
            </h1>
            <p className="max-w-lg text-[14px] leading-relaxed" style={{ color: C.grayFg }}>
              Quelques informations suffisent pour identifier les aides mobilisables
              pour votre projet.
            </p>
          </div>

          {mode === 'search' ? (
            <div className="space-y-4">
              <div
                className="rounded-2xl border p-5 sm:p-6"
                style={{
                  borderColor: C.border,
                  background: 'linear-gradient(135deg, var(--secondary) 0%, var(--card) 48%)',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <h2 className="mb-1 text-[18px]" style={{ fontFamily: SERIF, color: C.ink }}>
                  Où se trouve votre monument&nbsp;?
                </h2>
                <p className="mb-4 text-[14px]" style={{ color: C.grayFg }}>
                  Cherchez-le dans la base Mérimée&nbsp;: sa fiche sera pré-remplie
                  automatiquement.
                </p>
                <MerimeeSearch onSelect={handleMerimeeSelect} />
              </div>

              <button
                type="button"
                onClick={() => {
                  setPrefillData(null);
                  setMode('manual');
                }}
                className="group flex w-full items-center justify-between rounded-2xl border border-dashed px-6 py-4 text-left transition-colors hover:border-warning hover:bg-warning-muted"
                style={{ borderColor: C.border }}
              >
                <span>
                  <span className="block text-[15px] font-semibold" style={{ color: C.ink }}>
                    Mon monument n&rsquo;est pas dans la liste
                  </span>
                  <span className="mt-0.5 block text-[13px]" style={{ color: C.grayFg }}>
                    Décrivez-le vous-même en quelques champs simples.
                  </span>
                </span>
                <ArrowRight
                  className="h-5 w-5 shrink-0 transition-transform group-hover:translate-x-1"
                  style={{ color: C.orange }}
                />
              </button>
            </div>
          ) : (
            <div className="space-y-6">
              <button
                type="button"
                onClick={() => setMode('search')}
                className="text-[13px] underline-offset-2 hover:underline"
                style={{ color: C.grayMuted }}
              >
                ← Revenir à la recherche
              </button>
              <MonumentForm
                initialData={prefillData ?? undefined}
                onSubmit={handleFormSubmit}
                saving={saving}
              />
            </div>
          )}
        </div>
      )}

      {step === 2 && (
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
                {existingMonumentId ? 'Questionnaire' : 'Nouveau projet'}
              </div>
              <h1
                className="text-[clamp(1.4rem,3vw,1.8rem)] leading-tight"
                style={{ fontFamily: SERIF, color: C.ink }}
              >
                Précisons votre projet
              </h1>
              <p className="max-w-lg text-[14px] leading-relaxed" style={{ color: C.grayFg }}>
                Vos réponses affinent la liste des aides. Répondez librement&nbsp;—
                «&nbsp;Je ne sais pas&nbsp;» est une réponse tout à fait valable.
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
                  Vérifiez votre connexion puis réessayez&nbsp;— vos informations
                  monument sont bien enregistrées.
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
                Aucune précision supplémentaire n&rsquo;est nécessaire pour votre
                monument. Lancez le diagnostic pour découvrir les aides mobilisables.
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

      {step === 3 && <DiagnosticLoader />}
    </WizardShell>
  );
}
