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
import { MATERIAUX, TYPES_COUVERTURE } from '@/constants/monument-options';
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

    const lastTypo = lastOf(record.typologie_de_la_protection).toLowerCase();
    const protection: ProtectionLevel = lastTypo.includes('classé')
      ? 'classe'
      : lastTypo.includes('inscrit')
        ? 'inscrit'
        : 'non_protege';

    const regionValue = REGION_LABEL_TO_VALUE[record.region?.toLowerCase() ?? ''] ?? '';

    const titre = record.titre_editorial_de_la_notice ?? '';
    const denominationGuess = titre.toLowerCase().includes('église')
      ? 'eglise'
      : titre.toLowerCase().includes('château')
        ? 'chateau'
        : titre.toLowerCase().includes('chapelle')
          ? 'chapelle'
          : '';

    const materiauxRaw = lastOf(record.materiaux_de_la_couverture || record.materiaux_du_gros_oeuvre).toLowerCase();
    const materiaux = materiauxRaw
      ? MATERIAUX.filter((m) => materiauxRaw.includes(m.value)).map((m) => m.value)
      : undefined;

    const couvertureRaw = lastOf(record.type_de_couverture).toLowerCase();
    const typeCouverture = TYPES_COUVERTURE.find((t) => couvertureRaw.includes(t.value))?.value || undefined;

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
      denomination: denominationGuess,
      commune: record.commune_forme_index,
      departement: record.departement_en_lettres,
      region: regionValue as Region,
      protection,
      dateProtection,
      typeProtection,
      siecleConstruction: record.format_abrege_du_siecle_de_construction || record.siecle_de_la_campagne_principale_de_construction || undefined,
      typeCouverture,
      materiaux: materiaux?.length ? materiaux : undefined,
      descriptionGenerale: record.precision_de_la_protection || undefined,
    };

    console.log('=== MERIMEE RAW RECORD ===', JSON.stringify(record, null, 2));
    console.log('=== PREFILL DATA ===', JSON.stringify(prefill, null, 2));
    console.log('=== INTERMEDIATES ===', {
      materiauxRaw,
      materiaux,
      couvertureRaw,
      typeCouverture,
      lastDateEntry,
      dateProtection,
      denominationGuess,
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
        denomination: data.denomination ?? '',
        codePostal: data.codePostal ?? '',
        commune: data.commune ?? '',
        codeInsee: data.codeInsee ?? '',
        departement: data.departement ?? '',
        region: data.region ?? ('' as Region),
        protection: data.protection ?? 'non_protege',
        proprietaire: data.proprietaire ?? (user.segment === 'commune' ? 'public_commune' : 'prive_personne_physique'),
        etatConservation: data.etatConservation ?? 'moyen',
        referenceMerimee: data.referenceMerimee,
        coordonnees: data.coordonnees,
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

  if (showForm) {
    return (
      <div className="space-y-10">
        <div className="space-y-4">
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
          Ajoutez votre premier monument pour découvrir les aides disponibles.
        </p>
      </div>

      {/* tabs */}
      <Tabs defaultValue="merimee">
        <TabsList className="grid w-full grid-cols-2 h-12">
          <TabsTrigger value="merimee" className="gap-2 text-[14px]">
            <Search className="h-4 w-4" />
            Recherche PatriAlta
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
              Rechercher avec PatriAlta
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
              Votre monument n'est pas dans la base de PatriAlta ?
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
