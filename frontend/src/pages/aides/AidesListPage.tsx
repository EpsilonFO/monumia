import { useState, useCallback, useMemo } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { AideMatchBanner } from '@/components/aide/AideMatchBanner';
import { AideCard } from '@/components/aide/AideCard';
import { AideFilterBar } from '@/components/aide/AideFilterBar';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useAideStore } from '@/stores/useAideStore';
import { aideService } from '@/services/aide.service';
import { CheckCircle2, XCircle, Search } from 'lucide-react';
import type { AideDiagnosticResult } from '@/types';

export function AidesListPage() {
  const user = useAuthStore((s) => s.user);
  const monuments = useMonumentStore((s) => s.monuments);
  const filters = useAideStore((s) => s.filters);
  const lastDiagnostic = useAideStore((s) => s.lastDiagnostic);

  const userMonuments = useMemo(
    () => (user ? monuments.filter((m) => m.userId === user.id) : []),
    [monuments, user]
  );

  const [selectedMonumentId, setSelectedMonumentId] = useState(
    userMonuments[0]?.id ?? ''
  );
  const [isRunning, setIsRunning] = useState(false);

  const selectedMonument = useMemo(
    () => monuments.find((m) => m.id === selectedMonumentId),
    [monuments, selectedMonumentId]
  );

  const handleLaunchDiagnostic = useCallback(() => {
    if (!selectedMonument || !user) return;
    setIsRunning(true);

    setTimeout(() => {
      aideService.runDiagnostic(
        selectedMonument,
        user,
        filters.modeProjet,
        filters.travauxFiltres.length > 0 ? filters.travauxFiltres : undefined
      );
      setIsRunning(false);
    }, 800);
  }, [selectedMonument, user, filters.modeProjet, filters.travauxFiltres]);

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

  return (
    <div className="space-y-6">
      <PageHeader
        title="Diagnostic d'aides"
        description="Identifiez toutes les aides disponibles pour votre monument"
      />

      {userMonuments.length > 1 && (
        <Select value={selectedMonumentId} onValueChange={setSelectedMonumentId}>
          <SelectTrigger className="w-full sm:w-80">
            <SelectValue placeholder="Sélectionnez un monument" />
          </SelectTrigger>
          <SelectContent>
            {userMonuments.map((m) => (
              <SelectItem key={m.id} value={m.id}>
                {m.nom}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      <AideMatchBanner
        result={lastDiagnostic}
        isRunning={isRunning}
        onLaunch={handleLaunchDiagnostic}
        monumentName={selectedMonument?.nom}
      />

      {filteredResult && (
        <div className="space-y-6">
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
        </div>
      )}
    </div>
  );
}
