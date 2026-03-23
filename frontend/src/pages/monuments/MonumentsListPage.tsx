import { useEffect } from 'react';
import { Link } from 'react-router';
import { Plus, Castle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { MonumentCard } from '@/components/monument/MonumentCard';
import { useMonuments } from '@/hooks/useActiveMonument';
import { useAideStore } from '@/stores/useAideStore';
import { aideService } from '@/services/aide.service';

export function MonumentsListPage() {
  const { monuments, loading } = useMonuments();
  const diagnosticsByMonument = useAideStore((s) => s.diagnosticsByMonument);
  const setDiagnostic = useAideStore((s) => s.setDiagnostic);

  // Preload diagnostics for monuments not yet in the store
  useEffect(() => {
    for (const m of monuments) {
      if (!diagnosticsByMonument[m.id]) {
        aideService.getDiagnostics(m.id).then((diagnostics) => {
          if (diagnostics.length > 0) {
            setDiagnostic(m.id, diagnostics[0]);
          }
        }).catch(console.error);
      }
    }
  }, [monuments]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mes monuments"
        description="Gérez vos monuments historiques"
        action={
          <Button asChild>
            <Link to="/onboarding/monument">
              <Plus className="h-4 w-4 mr-2" />
              Ajouter un monument
            </Link>
          </Button>
        }
      />

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : monuments.length === 0 ? (
        <EmptyState
          icon={Castle}
          title="Aucun monument enregistré"
          description="Ajoutez votre premier monument pour commencer à identifier les aides disponibles."
          action={
            <Button asChild>
              <Link to="/onboarding/monument">
                <Plus className="h-4 w-4 mr-2" />
                Ajouter un monument
              </Link>
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {monuments.map((monument) => (
            <MonumentCard key={monument.id} monument={monument} />
          ))}
        </div>
      )}
    </div>
  );
}
