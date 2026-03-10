import { useState, useCallback, useMemo } from 'react';
import { LayoutGrid, List, FileText, Sparkles, CheckCircle2, XCircle, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { DossierPipeline } from '@/components/dossier/DossierPipeline';
import { DossierCard } from '@/components/dossier/DossierCard';
import { AideMatchBanner } from '@/components/aide/AideMatchBanner';
import { AideCard } from '@/components/aide/AideCard';
import { AideFilterBar } from '@/components/aide/AideFilterBar';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useAideStore } from '@/stores/useAideStore';
import { aideService } from '@/services/aide.service';
import type { AideDiagnosticResult } from '@/types';

export function DossiersListPage() {
  const user = useAuthStore((s) => s.user);
  const monuments = useMonumentStore((s) => s.monuments);
  const dossiers = useDossierStore((s) => s.dossiers);
  const filters = useAideStore((s) => s.filters);
  const lastDiagnostic = useAideStore((s) => s.lastDiagnostic);

  const userMonuments = useMemo(
    () => (user ? monuments.filter((m) => m.userId === user.id) : []),
    [monuments, user]
  );

  const userDossiers = useMemo(
    () => (user ? dossiers.filter((d) => d.userId === user.id) : []),
    [dossiers, user]
  );

  const [showMonumentPicker, setShowMonumentPicker] = useState(false);
  const [selectedMonumentId, setSelectedMonumentId] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [showDiagnostic, setShowDiagnostic] = useState(!!lastDiagnostic);

  const selectedMonument = useMemo(
    () => monuments.find((m) => m.id === selectedMonumentId),
    [monuments, selectedMonumentId]
  );

  const handleLaunchClick = () => {
    if (userMonuments.length === 0) return;
    if (userMonuments.length === 1) {
      setSelectedMonumentId(userMonuments[0].id);
      launchDiagnostic(userMonuments[0].id);
    } else {
      setSelectedMonumentId(userMonuments[0]?.id ?? '');
      setShowMonumentPicker(true);
    }
  };

  const launchDiagnostic = useCallback((monumentId: string) => {
    const monument = monuments.find((m) => m.id === monumentId);
    if (!monument || !user) return;
    setShowMonumentPicker(false);
    setIsRunning(true);
    setShowDiagnostic(true);

    setTimeout(() => {
      aideService.runDiagnostic(
        monument,
        user,
        filters.modeProjet,
        filters.travauxFiltres.length > 0 ? filters.travauxFiltres : undefined
      );
      setIsRunning(false);
    }, 800);
  }, [monuments, user, filters.modeProjet, filters.travauxFiltres]);

  const handleConfirmMonument = () => {
    if (selectedMonumentId) {
      launchDiagnostic(selectedMonumentId);
    }
  };

  const filteredResult = useMemo((): AideDiagnosticResult | null => {
    if (!lastDiagnostic) return null;

    const catFilter = filters.categories;
    const query = filters.searchQuery.toLowerCase();

    const filterMatches = (matches: typeof lastDiagnostic.aidesEligibles) => {
      let filtered = matches;
      if (catFilter.length > 0) {
        filtered = filtered.filter((m) => catFilter.includes(m.aide.categorie));
      }
      if (query) {
        filtered = filtered.filter(
          (m) =>
            m.aide.nom.toLowerCase().includes(query) ||
            m.aide.nomCourt.toLowerCase().includes(query) ||
            m.aide.organisme.toLowerCase().includes(query)
        );
      }
      return filtered;
    };

    return {
      ...lastDiagnostic,
      aidesEligibles: filterMatches(lastDiagnostic.aidesEligibles),
      aidesNonEligibles: filterMatches(lastDiagnostic.aidesNonEligibles),
    };
  }, [lastDiagnostic, filters.categories, filters.searchQuery]);

  const diagnosticMonument = useMemo(
    () => lastDiagnostic ? monuments.find((m) => m.id === lastDiagnostic.monumentId) : undefined,
    [lastDiagnostic, monuments]
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mes dossiers"
        description="Suivez l'avancement de vos demandes de financement"
        action={
          <Button onClick={handleLaunchClick} disabled={userMonuments.length === 0}>
            <Sparkles className="h-4 w-4 mr-2" />
            Lancer un diagnostic
          </Button>
        }
      />

      {/* Monument picker dialog */}
      <Dialog open={showMonumentPicker} onOpenChange={setShowMonumentPicker}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Choisir un monument</DialogTitle>
            <DialogDescription>
              Sur quel monument souhaitez-vous lancer le diagnostic d'aides ?
            </DialogDescription>
          </DialogHeader>
          <Select value={selectedMonumentId} onValueChange={setSelectedMonumentId}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Sélectionnez un monument" />
            </SelectTrigger>
            <SelectContent>
              {userMonuments.map((m) => (
                <SelectItem key={m.id} value={m.id}>
                  {m.nom} — {m.commune}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowMonumentPicker(false)}>
              Annuler
            </Button>
            <Button onClick={handleConfirmMonument} disabled={!selectedMonumentId}>
              <Sparkles className="h-4 w-4 mr-2" />
              Lancer le diagnostic
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Diagnostic results section */}
      {showDiagnostic && (
        <div className="space-y-6">
          <AideMatchBanner
            result={lastDiagnostic}
            isRunning={isRunning}
            onLaunch={handleLaunchClick}
            monumentName={diagnosticMonument?.nom ?? selectedMonument?.nom}
          />

          {filteredResult && (
            <>
              <AideFilterBar />

              <Tabs defaultValue="eligible">
                <TabsList>
                  <TabsTrigger value="eligible" className="gap-1.5">
                    <CheckCircle2 className="h-4 w-4" />
                    Éligibles ({filteredResult.aidesEligibles.length})
                  </TabsTrigger>
                  <TabsTrigger value="non-eligible" className="gap-1.5">
                    <XCircle className="h-4 w-4" />
                    Non éligibles ({filteredResult.aidesNonEligibles.length})
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="eligible" className="mt-4">
                  {filteredResult.aidesEligibles.length === 0 ? (
                    <EmptyState
                      icon={Search}
                      title="Aucune aide éligible trouvée"
                      description="Essayez de modifier les filtres ou vérifiez les informations de votre monument."
                    />
                  ) : (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                      {filteredResult.aidesEligibles.map((match) => (
                        <AideCard key={match.aide.id} match={match} />
                      ))}
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="non-eligible" className="mt-4">
                  {filteredResult.aidesNonEligibles.length === 0 ? (
                    <EmptyState
                      icon={CheckCircle2}
                      title="Toutes les aides sont éligibles"
                      description="Votre monument est éligible à toutes les aides analysées."
                    />
                  ) : (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                      {filteredResult.aidesNonEligibles.map((match) => (
                        <AideCard key={match.aide.id} match={match} />
                      ))}
                    </div>
                  )}
                </TabsContent>
              </Tabs>
            </>
          )}
        </div>
      )}

      {/* Existing dossiers */}
      {userDossiers.length === 0 && !showDiagnostic ? (
        <EmptyState
          icon={FileText}
          title="Aucun dossier en cours"
          description="Lancez un diagnostic d'aides pour identifier les financements disponibles et créer votre premier dossier."
          action={
            <Button onClick={handleLaunchClick} disabled={userMonuments.length === 0}>
              <Sparkles className="h-4 w-4 mr-2" />
              Lancer un diagnostic
            </Button>
          }
        />
      ) : userDossiers.length > 0 ? (
        <div className="space-y-4">
          {showDiagnostic && (
            <h2 className="text-lg font-semibold pt-4 border-t">Dossiers en cours</h2>
          )}
          <Tabs defaultValue="pipeline">
            <TabsList>
              <TabsTrigger value="pipeline" className="gap-1.5">
                <LayoutGrid className="h-4 w-4" />
                Pipeline
              </TabsTrigger>
              <TabsTrigger value="list" className="gap-1.5">
                <List className="h-4 w-4" />
                Liste
              </TabsTrigger>
            </TabsList>

            <TabsContent value="pipeline" className="mt-4">
              <DossierPipeline dossiers={userDossiers} />
            </TabsContent>

            <TabsContent value="list" className="mt-4">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {userDossiers.map((dossier) => (
                  <DossierCard key={dossier.id} dossier={dossier} />
                ))}
              </div>
            </TabsContent>
          </Tabs>
        </div>
      ) : null}
    </div>
  );
}
