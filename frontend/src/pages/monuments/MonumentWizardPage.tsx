import { useState } from 'react';
import { useNavigate } from 'react-router';
import { ArrowRight } from 'lucide-react';
import { MerimeeSearch } from '@/components/monument/MerimeeSearch';
import { MonumentForm } from '@/components/monument/MonumentForm';
import { PerilStep } from '@/components/project/wizard/PerilStep';
import { WizardShell } from '@/components/project/wizard/WizardShell';
import {
  MONUMENT_WIZARD_STEPS,
  type WizardStepKey,
} from '@/components/project/wizard/WizardRail';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { monumentService } from '@/services/monument.service';
import { merimeeService } from '@/services/merimee.service';
import { REGIONS } from '@/constants/regions';
import { ROUTES } from '@/constants/routes';
import { C, SERIF } from '@/lib/brand';
import { toast } from 'sonner';
import type { MerimeeRecord, Monument, ProtectionLevel, Region } from '@/types';

const REGION_LABEL_TO_VALUE: Record<string, string> = Object.fromEntries(
  REGIONS.map((r) => [r.label.toLowerCase(), r.value])
);

const EYEBROW = 'Nouveau monument';

/**
 * Création d'un MONUMENT : sa fiche, puis son état sanitaire. Rien du chantier
 * ici — les travaux, les intentions et le questionnaire appartiennent au projet
 * et se saisissent dans le wizard projet, une fois le monument décrit.
 *
 * Sortie : la page du monument, onglet « Projets », dont l'état vide porte le
 * CTA « Lancer un projet de travaux ».
 */
export function MonumentWizardPage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const addMonument = useMonumentStore((s) => s.addMonument);
  const updateMonument = useMonumentStore((s) => s.updateMonument);
  const setActiveMonument = useMonumentStore((s) => s.setActiveMonument);

  const [step, setStep] = useState<WizardStepKey>('fiche');
  const [mode, setMode] = useState<'search' | 'manual'>('search');
  const [prefillData, setPrefillData] = useState<Partial<Monument> | null>(null);
  const [saving, setSaving] = useState(false);
  const [monument, setMonument] = useState<Monument | null>(null);
  const [peril, setPeril] = useState<boolean | null>(null);

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

      // Matériaux et type de couverture ne sont plus préremplis : leurs
      // colonnes ont été droppées (migration 20260516174303) et aucune aide ne
      // les lit. Les extraire de Mérimée ne remplissait plus rien.
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
      const created = await monumentService.create({
        nom: data.nom ?? 'Mon monument',
        commune: data.commune ?? '',
        codeInsee: data.codeInsee ?? '',
        protection: data.protection ?? 'non_protege',
        // Le formulaire impose le type de propriétaire (champ requis) : ce
        // repli ne sert qu'à satisfaire le type.
        proprietaire: data.proprietaire ?? 'prive_personne_physique',
        referenceMerimee: data.referenceMerimee,
        dateProtection: data.dateProtection,
        typeProtection: data.typeProtection,
        siecleConstruction: data.siecleConstruction,
        descriptionGenerale: data.descriptionGenerale,
        // L'état sanitaire est posé à l'étape suivante, après la création (cf.
        // migration 20260827094119, qui rend etat_conservation nullable) : y
        // écrire un repli produirait une fausse donnée.
      });

      addMonument(created);
      setActiveMonument(created.id);
      setMonument(created);
      setStep('sanitaire');
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Erreur lors de la création du monument'
      );
    } finally {
      setSaving(false);
    }
  };

  // Fin du parcours : on enregistre l'état sanitaire sur la fiche puis on part
  // sur l'onglet « Projets », vide, dont le CTA invite à lancer un chantier.
  // Échec = on reste sur l'écran : partir sans la réponse priverait
  // silencieusement le monument des dispositifs d'urgence.
  const handlePerilNext = async () => {
    if (!monument || peril === null) return;
    setSaving(true);
    try {
      const updated = await monumentService.update(monument.id, {
        etatConservation: peril ? 'peril' : 'bon',
      });
      updateMonument(monument.id, updated);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Erreur lors de l’enregistrement de l’état du monument"
      );
      return;
    } finally {
      setSaving(false);
    }
    navigate(`${ROUTES.MONUMENT_DETAIL(monument.id)}?tab=projets`);
  };

  return (
    <WizardShell
      steps={MONUMENT_WIZARD_STEPS}
      step={step}
      monument={monument}
      progress={null}
      // La fiche est déjà enregistrée à l'étape 2 : quitter ne perd que la
      // réponse sur le péril, modifiable ensuite depuis la fiche sanitaire.
      confirmQuit={false}
      exitTo={monument ? ROUTES.MONUMENT_DETAIL(monument.id) : ROUTES.MONUMENTS}
    >
      {step === 'fiche' && (
        <div className="space-y-4">
          <div className="space-y-1.5">
            <div
              className="text-[12px] font-semibold uppercase tracking-[0.2em]"
              style={{ color: C.orange }}
            >
              {EYEBROW}
            </div>
            <h1
              className="text-[clamp(1.5rem,3.2vw,2rem)] leading-tight"
              style={{ fontFamily: SERIF, color: C.ink }}
            >
              Commençons par votre monument
            </h1>
            <p className="max-w-lg text-[14px] leading-relaxed" style={{ color: C.grayFg }}>
              Quelques informations suffisent. Vous lancerez ensuite autant de projets de
              travaux que vous le souhaitez sur cette fiche.
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

      {step === 'sanitaire' && (
        <PerilStep
          eyebrow={EYEBROW}
          value={peril}
          onChange={setPeril}
          onNext={handlePerilNext}
          saving={saving}
        />
      )}
    </WizardShell>
  );
}
