import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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
import { Compass, Search, PenLine, ChevronLeft } from 'lucide-react';
import { toast } from 'sonner';
import type { MerimeeRecord, Monument, ProtectionLevel, Region } from '@/types';

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
    // The search endpoint only returns basic fields — fetch the full record
    const fullRecord = await merimeeService.getByReference(searchRecord.reference);
    const record = fullRecord ?? searchRecord;

    // Helper: take last segment after ";" (most recent/relevant value)
    const lastOf = (s: string | undefined) => s?.split(';').pop()?.trim() ?? '';

    // Protection level — last segment containing "classé" or "inscrit"
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

    // Parse materiaux: last segment, match keywords against our list
    const materiauxRaw = lastOf(record.materiaux_de_la_couverture || record.materiaux_du_gros_oeuvre).toLowerCase();
    const materiaux = materiauxRaw
      ? MATERIAUX.filter((m) => materiauxRaw.includes(m.value)).map((m) => m.value)
      : undefined;

    // Match type_de_couverture: last segment against our TYPES_COUVERTURE list
    const couvertureRaw = lastOf(record.type_de_couverture).toLowerCase();
    const typeCouverture = TYPES_COUVERTURE.find((t) => couvertureRaw.includes(t.value))?.value || undefined;

    // Parse date de protection: last segment, split on ":", extract date part
    let dateProtection: string | undefined;
    const lastDateEntry = lastOf(record.date_et_typologie_de_la_protection);
    if (lastDateEntry) {
      const datePart = lastDateEntry.split(':')[0]?.trim() ?? '';
      if (/^\d{4}\/\d{2}\/\d{2}$/.test(datePart)) {
        dateProtection = datePart.replace(/\//g, '-');
      }
    }

    // typeProtection: last segment
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
      // Siècles et descriptions : on garde la valeur complète
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

      // Upload photos: storage + document record + monument JSONB
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
      <div className="space-y-6">
        <div className="text-center space-y-2">
          <div className="mx-auto mb-2 flex items-center justify-center w-12 h-12 rounded-full bg-accent/20">
            <Compass className="h-6 w-6 text-accent" />
          </div>
          <h1 className="text-2xl font-bold">Complétez la fiche</h1>
          <p className="text-muted-foreground">
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
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <h1 className="text-2xl font-bold">Votre monument</h1>
        <p className="text-muted-foreground">
          Ajoutez votre premier monument pour découvrir les aides disponibles.
        </p>
      </div>

      <Tabs defaultValue="merimee">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="merimee" className="gap-2">
            <Search className="h-4 w-4" />
            Recherche Mérimée
          </TabsTrigger>
          <TabsTrigger value="manual" className="gap-2">
            <PenLine className="h-4 w-4" />
            Saisie manuelle
          </TabsTrigger>
        </TabsList>

        <TabsContent value="merimee" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Base Mérimée</CardTitle>
              <CardDescription>
                Recherchez votre monument dans la base nationale du patrimoine.
                Les informations seront pré-remplies automatiquement.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <MerimeeSearch onSelect={handleMerimeeSelect} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="manual" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Saisie manuelle</CardTitle>
              <CardDescription>
                Votre monument n'est pas dans la base Mérimée ?
                Renseignez ses informations manuellement.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button onClick={() => setShowForm(true)}>
                Créer une fiche monument
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <div className="flex justify-start">
        <Button variant="outline" onClick={() => navigate(-1)}>
          <ChevronLeft className="h-4 w-4 mr-1" />
          Retour
        </Button>
      </div>
    </div>
  );
}
