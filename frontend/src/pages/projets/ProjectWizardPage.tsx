import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { MerimeeSearch } from '@/components/monument/MerimeeSearch';
import { MonumentForm } from '@/components/monument/MonumentForm';
import { ProjectQuestionnaire } from '@/components/project/ProjectQuestionnaire';
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
import { Search, PenLine, ArrowRight, Check, Loader2 } from 'lucide-react';
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

type WizardStep = 1 | 2 | 3;

const STEP_LABELS: Record<WizardStep, string> = {
  1: 'Le monument',
  2: 'Votre projet',
  3: 'Diagnostic',
};

export function ProjectWizardPage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const addMonument = useMonumentStore((s) => s.addMonument);
  const setActiveMonument = useMonumentStore((s) => s.setActiveMonument);
  const setDiagnostic = useAideStore((s) => s.setDiagnostic);

  const [step, setStep] = useState<WizardStep>(1);
  const [prefillData, setPrefillData] = useState<Partial<Monument> | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [monumentId, setMonumentId] = useState<string | null>(null);
  const [answers, setAnswers] = useState<ProjectQuestionnaireAnswers>({});
  // Questionnaire du moteur d'aides : on lance un premier diagnostic déterministe
  // (sans réponses) dès l'étape 2 pour obtenir les questions à poser (faits
  // manquants) et le résultat de base. Les réponses ne sont jamais renvoyées au
  // moteur : elles se résolvent côté client via eliminationsParOption.
  const [questions, setQuestions] = useState<QcmQuestion[]>([]);
  const [baseResult, setBaseResult] = useState<AideDiagnosticResult | null>(null);
  const [loadingQuestions, setLoadingQuestions] = useState(false);

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
      setShowForm(true);
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
    if (step !== 2 || !monumentId || baseResult) return;
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
        if (!cancelled)
          toast.error('Impossible de charger le questionnaire. Vous pourrez le lancer depuis le projet.');
      })
      .finally(() => {
        if (!cancelled) setLoadingQuestions(false);
      });
    return () => {
      cancelled = true;
    };
  }, [step, monumentId, baseResult]);

  // Étape 2 → projet : on persiste les réponses sur le monument (la page projet
  // recalcule le même diagnostic à partir de là), on résout le QCM côté client
  // (eliminationsParOption) et on amorce le store pour éviter un écran vide.
  const handleQuestionnaireNext = async () => {
    if (!monumentId) return;
    setSaving(true);
    try {
      await monumentService.update(monumentId, { questionnaire: answers });
    } catch (err) {
      // Column may not exist yet (pre-migration) — degrade gracefully.
      console.error('Erreur enregistrement questionnaire (ignorée):', err);
    }
    // Ré-évaluation déterministe AVEC les réponses : c'est ici que les user_fact
    // satisfaits promeuvent les aides en éligibles. On amorce le store pour
    // éviter un écran vide à l'arrivée (la page projet recalcule à l'identique).
    try {
      setDiagnostic(monumentId, await aideService.runProjectDiagnostic(monumentId, answers));
    } catch (err) {
      console.error('Erreur diagnostic:', err);
    }
    // Leave `saving` true through the navigation — the component unmounts.
    navigate(ROUTES.PROJET_DETAIL(monumentId));
  };

  const StepIndicator = (
    <div className="flex items-center gap-3">
      {([1, 2, 3] as WizardStep[]).map((s, i) => {
        const done = s < step;
        const current = s === step;
        return (
          <div key={s} className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span
                className="flex h-7 w-7 items-center justify-center rounded-full text-[12px] font-semibold transition-colors"
                style={{
                  background: done || current ? C.orange : 'transparent',
                  border: `1px solid ${done || current ? C.orange : C.border}`,
                  color: done || current ? '#fff' : C.ink,
                }}
              >
                {done ? <Check className="h-3.5 w-3.5" strokeWidth={3} /> : s}
              </span>
              <span
                className="hidden text-[13px] sm:inline"
                style={{ color: current ? C.ink : '#6a7180', fontWeight: current ? 600 : 400 }}
              >
                {STEP_LABELS[s]}
              </span>
            </div>
            {i < 2 && <span className="h-px w-6" style={{ background: C.border }} />}
          </div>
        );
      })}
    </div>
  );

  return (
    <div className="min-h-screen" style={{ background: C.cream }}>
      <div className="mx-auto max-w-3xl px-5 py-10 space-y-10">
        <div className="space-y-6">
          {StepIndicator}
          <div className="space-y-2">
            <div
              className="text-[12px] font-semibold uppercase tracking-[0.2em]"
              style={{ color: C.orange }}
            >
              Nouveau projet
            </div>
            <h1
              className="text-[clamp(1.8rem,4vw,2.4rem)]"
              style={{ fontFamily: SERIF, color: C.ink }}
            >
              {step === 1 && 'Ajoutez votre monument'}
              {step === 2 && 'Précisez votre projet'}
            </h1>
          </div>
        </div>

        {step === 1 &&
          (showForm ? (
            <div className="space-y-6">
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="text-[13px] underline-offset-2 hover:underline"
                style={{ color: '#6a7180' }}
              >
                ← Changer de méthode
              </button>
              <MonumentForm
                initialData={prefillData ?? undefined}
                onSubmit={handleFormSubmit}
                saving={saving}
              />
            </div>
          ) : (
            <Tabs defaultValue="merimee">
              <TabsList className="grid h-12 w-full grid-cols-2">
                <TabsTrigger value="merimee" className="gap-2 text-[14px]">
                  <Search className="h-4 w-4" />
                  Rechercher (Mérimée)
                </TabsTrigger>
                <TabsTrigger value="manual" className="gap-2 text-[14px]">
                  <PenLine className="h-4 w-4" />
                  Saisie manuelle
                </TabsTrigger>
              </TabsList>

              <TabsContent value="merimee" className="mt-6">
                <div
                  className="rounded-xl border p-8"
                  style={{ borderColor: C.border, background: C.card }}
                >
                  <h3
                    className="mb-2 text-[20px]"
                    style={{ fontFamily: SERIF, color: C.ink }}
                  >
                    Rechercher dans la base Mérimée
                  </h3>
                  <p className="mb-6 text-[14px]" style={{ color: '#6a7180' }}>
                    Les informations connues de votre monument seront pré-remplies
                    automatiquement.
                  </p>
                  <MerimeeSearch onSelect={handleMerimeeSelect} />
                </div>
              </TabsContent>

              <TabsContent value="manual" className="mt-6">
                <div
                  className="rounded-xl border p-8"
                  style={{ borderColor: C.border, background: C.card }}
                >
                  <h3
                    className="mb-2 text-[20px]"
                    style={{ fontFamily: SERIF, color: C.ink }}
                  >
                    Saisie manuelle
                  </h3>
                  <p className="mb-6 text-[14px]" style={{ color: '#6a7180' }}>
                    Votre monument n'est pas dans la base ? Renseignez ses informations
                    manuellement.
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      setPrefillData(null);
                      setShowForm(true);
                    }}
                    className="group inline-flex items-center gap-2 rounded-lg px-6 py-3 text-[14px] font-semibold text-white transition-all hover:shadow-lg"
                    style={{ background: C.orange }}
                  >
                    Créer une fiche monument
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                  </button>
                </div>
              </TabsContent>
            </Tabs>
          ))}

        {step === 2 && (
          <div className="space-y-8">
            {loadingQuestions ? (
              <div className="flex items-center gap-3 py-10 text-[14px]" style={{ color: '#6a7180' }}>
                <Loader2 className="h-4 w-4 animate-spin" style={{ color: C.blueLight }} />
                Analyse de votre monument…
              </div>
            ) : questions.length === 0 ? (
              <p className="text-[15px] leading-relaxed" style={{ color: '#6a7180' }}>
                Aucune précision supplémentaire n'est nécessaire pour votre monument. Lancez le
                diagnostic pour découvrir les aides mobilisables.
              </p>
            ) : (
              <>
                <p className="text-[15px] leading-relaxed" style={{ color: '#6a7180' }}>
                  Quelques questions pour affiner les aides proposées. Vous pourrez les modifier
                  plus tard.
                </p>
                <ProjectQuestionnaire questions={questions} value={answers} onChange={setAnswers} />
              </>
            )}
            <div className="flex justify-end">
              <button
                type="button"
                disabled={saving || loadingQuestions}
                onClick={handleQuestionnaireNext}
                className="group inline-flex items-center gap-2 rounded-lg px-6 py-3 text-[14px] font-semibold text-white transition-all hover:shadow-lg disabled:opacity-60"
                style={{ background: C.orange }}
              >
                {saving ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Analyse des aides en cours…
                  </>
                ) : (
                  <>
                    {questions.length === 0 ? 'Voir les aides' : 'Lancer le diagnostic'}
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
