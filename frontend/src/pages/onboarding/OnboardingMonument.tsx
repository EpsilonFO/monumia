import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { MerimeeSearch } from '@/components/monument/MerimeeSearch';
import { MonumentForm } from '@/components/monument/MonumentForm';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { monumentService } from '@/services/monument.service';
import { REGIONS } from '@/constants/regions';
import { MATERIAUX } from '@/constants/monument-options';
import { Sparkles, Search, PenLine, ChevronLeft } from 'lucide-react';
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

  const handleMerimeeSelect = (record: MerimeeRecord) => {
    const typo = record.typologie_de_la_protection?.toLowerCase() ?? '';
    const protection: ProtectionLevel = typo.includes('classé')
      ? 'classe'
      : typo.includes('inscrit')
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

    // Parse materiaux: match keywords from Mérimée free-text against our list
    const materiauxRaw = (record.materiaux_de_la_couverture || record.materiaux_du_gros_oeuvre || '').toLowerCase();
    const materiaux = materiauxRaw
      ? MATERIAUX.filter((m) => materiauxRaw.includes(m.value)).map((m) => m.value)
      : undefined;

    setPrefillData({
      nom: titre,
      referenceMerimee: record.reference,
      denomination: denominationGuess,
      commune: record.commune_forme_index,
      departement: record.departement_en_lettres,
      region: regionValue as Region,
      protection,
      typeProtection: record.date_et_typologie_de_la_protection || record.typologie_de_la_protection || undefined,
      siecleConstruction: record.siecle_de_la_campagne_principale_de_construction || undefined,
      typeCouverture: record.type_de_couverture || undefined,
      materiaux: materiaux?.length ? materiaux : undefined,
      descriptionGenerale: record.precision_de_la_protection || undefined,
    });
    setShowForm(true);
  };

  const handleFormSubmit = async (data: Partial<Monument>) => {
    if (!user) return;
    setSaving(true);
    try {
      const monument = await monumentService.create({
        nom: data.nom ?? 'Mon monument',
        denomination: data.denomination ?? '',
        adresse: data.adresse ?? '',
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

      addMonument(monument);
      setActiveMonument(monument.id);
      completeOnboarding();
      navigate('/');
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
            <Sparkles className="h-6 w-6 text-accent" />
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
