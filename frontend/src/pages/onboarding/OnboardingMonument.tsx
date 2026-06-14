import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { MerimeeSearch } from '@/components/monument/MerimeeSearch';
import { MonumentForm, type PendingPhoto } from '@/components/monument/MonumentForm';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { monumentService } from '@/services/monument.service';

import { merimeeService } from '@/services/merimee.service';
import { REGIONS } from '@/constants/regions';
import { Search, PenLine, ChevronLeft, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';
import type { MerimeeRecord, Monument, ProtectionLevel, Region } from '@/types';

const C = {
  bg: '#F8F7F4',
  bgAlt: '#FFFFFF',
  text: '#1B1E2E',
  textMuted: '#5C6178',
  textLight: '#8E92A4',
  royal: '#1A237E',
  terra: '#C75B3A',
  border: '#E4E2DC',
} as const;

const REGION_LABEL_TO_VALUE: Record<string, string> = Object.fromEntries(
  REGIONS.map((r) => [r.label.toLowerCase(), r.value])
);

export function OnboardingMonument() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const completeOnboarding = useAuthStore((s) => s.completeOnboarding);
  const addMonument = useMonumentStore((s) => s.addMonument);
  const setActiveMonument = useMonumentStore((s) => s.setActiveMonument);
  const [prefillData, setPrefillData] = useState<Partial<Monument> | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleMerimeeSelect = async (searchRecord: MerimeeRecord) => {
    const fullRecord = await merimeeService.getByReference(searchRecord.reference);
    const record = fullRecord ?? searchRecord;

    const lastOf = (s: string | undefined) => s?.split(';').pop()?.trim() ?? '';

    // Mérimée concatenates protection statuses with `;` in chronological order
    // (e.g. "classé MH partiellement;inscrit MH partiellement;protection partielle"
    // means the monument was classé, then re-inscrit — so it is currently inscrit).
    // Walk the list and keep the LAST entry that names a classement/inscription;
    // free-form descriptions like "protection partielle" don't override it.
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
      'commune': 'public_commune',
      'communal': 'public_commune',
      'département': 'public_departement',
      'departemental': 'public_departement',
      'région': 'public_region',
      'regional': 'public_region',
      'état': 'public_etat',
      'etat': 'public_etat',
      'propriété privée': 'prive_personne_physique',
      'privé': 'prive_personne_physique',
      'prive': 'prive_personne_physique',
      'sci': 'prive_sci',
      'association': 'association',
      'mixte': 'mixte',
    };
    const statutRaw = record.statut_juridique_de_l_edifice?.toLowerCase().trim() ?? '';
    const proprietaireGuess =
      PROPRIETAIRE_MAP[statutRaw] ??
      (Object.entries(PROPRIETAIRE_MAP).find(([k]) => statutRaw.includes(k))?.[1]) ??
      undefined;

    let dateProtection: string | undefined;
    const lastDateEntry = lastOf(record.date_et_typologie_de_la_protection);
    if (lastDateEntry) {
      const datePart = lastDateEntry.split(':')[0]?.trim() ?? '';
      if (/^\d{4}\/\d{2}\/\d{2}$/.test(datePart)) {
        dateProtection = datePart.replace(/\//g, '-');
      }
    }

    const typeProtection = lastOf(record.date_et_typologie_de_la_protection) || lastOf(record.typologie_de_la_protection) || undefined;

    const prefill = {
      nom: titre,
      referenceMerimee: record.reference,
      commune: record.commune_actuelle || record.commune_forme_index,
      codeInsee: record.cog_insee_lors_de_la_protection || undefined,
      departement: record.departement_en_lettres,
      region: regionValue as Region,
      protection,
      dateProtection,
      typeProtection,
      siecleConstruction: record.format_abrege_du_siecle_de_construction || record.siecle_de_la_campagne_principale_de_construction || undefined,
      proprietaire: proprietaireGuess,
      descriptionGenerale: record.precision_de_la_protection || undefined,
    };

    console.log('=== MERIMEE RAW RECORD ===', JSON.stringify(record, null, 2));
    console.log('=== PREFILL DATA ===', JSON.stringify(prefill, null, 2));
    console.log('=== INTERMEDIATES ===', {
      lastDateEntry,
      dateProtection,
      regionValue,
    });

    setPrefillData(prefill);
    setShowForm(true);
  };

  const uploadDocument = useDocumentStore((s) => s.uploadDocument);

  const handleFormSubmit = async (data: Partial<Monument>, pendingPhotos: PendingPhoto[]) => {
    if (!user) return;
    setSaving(true);
    try {
      const monument = await monumentService.create({
        nom: data.nom ?? 'Mon monument',
        commune: data.commune ?? '',
        codeInsee: data.codeInsee ?? '',
        protection: data.protection ?? 'non_protege',
        proprietaire: data.proprietaire ?? (user.segment === 'commune' ? 'public_commune' : 'prive_personne_physique'),
        etatConservation: data.etatConservation ?? 'moyen',
        referenceMerimee: data.referenceMerimee,
        dateProtection: data.dateProtection,
        typeProtection: data.typeProtection,
        siecleConstruction: data.siecleConstruction,
        descriptionGenerale: data.descriptionGenerale,
        travauxEnvisages: data.travauxEnvisages,
      });

      for (const photo of pendingPhotos) {
        try {
          const doc = await uploadDocument({
            file: photo.file,
            nom: photo.nom || `Photo — ${data.nom ?? 'Monument'}`,
            type: 'photo',
            monumentId: monument.id,
          }, user.id);
          await monumentService.addPhoto(monument.id, {
            url: doc.url,
            legende: photo.nom || photo.file.name.replace(/\.[^.]+$/, ''),
            type: 'autre',
          });
        } catch (err) {
          console.error('Erreur upload photo:', err);
        }
      }

      addMonument(monument);
      setActiveMonument(monument.id);
      completeOnboarding();
      navigate('/app');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors de la création du monument');
    } finally {
      setSaving(false);
    }
  };

  const backToMonuments = (
    <button
      type="button"
      onClick={() => navigate('/app/monuments')}
      className="fixed left-6 z-40 inline-flex items-center gap-2 px-5 py-3 text-[15px] font-medium hover:opacity-70 transition-opacity"
      style={{ top: '92px', color: C.text, background: C.bg, border: `1px solid ${C.bg}` }}
    >
      <ChevronLeft className="h-5 w-5" />
      Retour aux monuments
    </button>
  );

  if (showForm) {
    return (
      <div className="space-y-10">
        <div className="space-y-4">
          {backToMonuments}
          <div className="flex items-center gap-3">
            <span className="h-px w-12" style={{ background: C.terra }} />
            <span className="text-[13px] font-semibold uppercase tracking-[0.2em]" style={{ color: C.terra }}>
              Fiche monument
            </span>
          </div>
          <h1
            className="text-[clamp(1.8rem,4vw,2.5rem)] font-light tracking-[-0.02em]"
            style={{ fontFamily: "'Cormorant Garamond', serif", color: C.text }}
          >
            Complétez la fiche
          </h1>
          <p className="text-[16px] leading-[1.75]" style={{ color: C.textMuted }}>
            {prefillData?.referenceMerimee
              ? 'Les informations Mérimée ont été pré-remplies. Complétez les champs restants.'
              : 'Renseignez les informations de votre monument.'}
          </p>
        </div>

        <MonumentForm initialData={prefillData ?? undefined} onSubmit={handleFormSubmit} saving={saving} />
      </div>
    );
  }

  return (
    <div className="space-y-10">
      {/* heading */}
      <div className="space-y-4">
        {backToMonuments}
        <div className="flex items-center gap-3">
          <span className="h-px w-12" style={{ background: C.terra }} />
          <span className="text-[13px] font-semibold uppercase tracking-[0.2em]" style={{ color: C.terra }}>
            Étape 3
          </span>
        </div>
        <h1
          className="text-[clamp(1.8rem,4vw,2.5rem)] font-light tracking-[-0.02em]"
          style={{ fontFamily: "'Cormorant Garamond', serif", color: C.text }}
        >
          Votre <em className="italic" style={{ color: C.royal }}>monument</em>
        </h1>
        <p className="text-[16px] leading-[1.75]" style={{ color: C.textMuted }}>
          Ajoutez votre monument pour découvrir les aides disponibles.
        </p>
      </div>

      {/* tabs */}
      <Tabs defaultValue="merimee">
        <TabsList className="grid w-full grid-cols-2 h-12">
          <TabsTrigger value="merimee" className="gap-2 text-[14px]">
            <Search className="h-4 w-4" />
            Recherche Monumia
          </TabsTrigger>
          <TabsTrigger value="manual" className="gap-2 text-[14px]">
            <PenLine className="h-4 w-4" />
            Saisie manuelle
          </TabsTrigger>
        </TabsList>

        <TabsContent value="merimee" className="mt-6">
          <div className="border p-8" style={{ borderColor: C.border, background: C.bgAlt }}>
            <h3
              className="text-[20px] font-normal mb-2"
              style={{ fontFamily: "'Cormorant Garamond', serif", color: C.text }}
            >
              Rechercher avec Monumia
            </h3>
            <p className="text-[14px] mb-6" style={{ color: C.textLight }}>
              Recherchez votre monument dans une base de données connue.
              Les informations seront pré-remplies automatiquement.
            </p>
            <MerimeeSearch onSelect={handleMerimeeSelect} />
          </div>
        </TabsContent>

        <TabsContent value="manual" className="mt-6">
          <div className="border p-8" style={{ borderColor: C.border, background: C.bgAlt }}>
            <h3
              className="text-[20px] font-normal mb-2"
              style={{ fontFamily: "'Cormorant Garamond', serif", color: C.text }}
            >
              Saisie manuelle
            </h3>
            <p className="text-[14px] mb-6" style={{ color: C.textLight }}>
              Votre monument n'est pas dans la base de Monumia ?
              Renseignez ses informations manuellement.
            </p>
            <button
              onClick={() => setShowForm(true)}
              className="group flex items-center gap-2 px-6 py-3 text-[14px] font-semibold text-white transition-all duration-300 hover:shadow-lg"
              style={{ background: C.royal }}
            >
              Créer une fiche monument
              <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
            </button>
          </div>
        </TabsContent>
      </Tabs>

      {/* back button */}
      <div className="flex justify-start">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 px-5 py-3 text-[14px] font-medium border transition-all duration-300 hover:bg-[#F8F7F4]"
          style={{ borderColor: C.border, color: C.textMuted }}
        >
          <ChevronLeft className="h-4 w-4" />
          Retour
        </button>
      </div>
    </div>
  );
}
