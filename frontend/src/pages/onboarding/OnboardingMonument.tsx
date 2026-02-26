import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { MerimeeSearch } from '@/components/monument/MerimeeSearch';
import { MonumentForm } from '@/components/monument/MonumentForm';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { REGIONS } from '@/constants/regions';
import { generateId } from '@/lib/format-utils';
import { Sparkles, Search, PenLine, ChevronLeft } from 'lucide-react';
import type { MerimeeRecord, Monument, ProtectionLevel, Region } from '@/types';

export function OnboardingMonument() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const completeOnboarding = useAuthStore((s) => s.completeOnboarding);
  const addMonument = useMonumentStore((s) => s.addMonument);
  const setActiveMonument = useMonumentStore((s) => s.setActiveMonument);
  const [prefillData, setPrefillData] = useState<Partial<Monument> | null>(null);
  const [showForm, setShowForm] = useState(false);

  const handleMerimeeSelect = (record: MerimeeRecord) => {
    const protectionMap: Record<string, ProtectionLevel> = {
      'Classé MH': 'classe',
      'Inscrit MH': 'inscrit',
    };

    const region = REGIONS.find((r) =>
      (r.departements as readonly string[]).includes(record.departement)
    );

    setPrefillData({
      nom: record.denomination,
      referenceMerimee: record.reference,
      denomination: record.denomination.toLowerCase().includes('église')
        ? 'eglise'
        : record.denomination.toLowerCase().includes('château')
          ? 'chateau'
          : record.denomination.toLowerCase().includes('chapelle')
            ? 'chapelle'
            : '',
      adresse: record.adresse,
      commune: record.commune,
      departement: record.departement,
      region: (region?.value ?? '') as Region,
      coordonnees: record.coordonnees,
      protection: protectionMap[record.protection] ?? 'non_protege',
      dateProtection: record.dateProtection,
      typeProtection: record.protection,
      siecleConstruction: record.siecle,
      descriptionGenerale: record.description,
    });
    setShowForm(true);
  };

  const handleFormSubmit = (data: Partial<Monument>) => {
    if (!user) return;

    const now = new Date().toISOString();
    const monument: Monument = {
      id: `mon-${generateId()}`,
      userId: user.id,
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
      photos: data.photos ?? [],
      completionPercentage: 50,
      createdAt: now,
      updatedAt: now,
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
    };

    addMonument(monument);
    setActiveMonument(monument.id);
    completeOnboarding();
    navigate('/');
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

        <MonumentForm initialData={prefillData ?? undefined} onSubmit={handleFormSubmit} />
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
