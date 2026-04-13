import { useEffect } from 'react';
import { Link } from 'react-router';
import { Plus, Church, Loader2 } from 'lucide-react';
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

  useEffect(() => {
    for (const m of monuments) {
      if (!diagnosticsByMonument[m.id]) {
        aideService.getDiagnostics(m.id).then((diagnostics) => {
          if (diagnostics.length > 0) setDiagnostic(m.id, diagnostics[0]);
        }).catch(console.error);
      }
    }
  }, [monuments]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mes monumentss"
        description="Gérez vos monuments historiques"
        action={
          <Link
            to="/onboarding/monument"
            className="inline-flex items-center gap-2 px-5 py-2.5 text-[13px] font-semibold text-white rounded-lg transition-all duration-300 hover:shadow-md"
            style={{ background: '#C75B3A' }}
          >
            <Plus className="h-3.5 w-3.5" strokeWidth={2} />
            Ajouter un monument
          </Link>
        }
      />

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin text-[#8E92A4]" />
        </div>
      ) : monuments.length === 0 ? (
        <EmptyState
          icon={Church}
          title="Aucun monument enregistré"
          description="Ajoutez votre premier monument pour commencer à identifier les aides disponibles."
          action={
            <Link
              to="/onboarding/monument"
              className="inline-flex items-center gap-2 px-5 py-2.5 text-[13px] font-semibold text-white rounded-lg transition-all duration-300 hover:shadow-md"
              style={{ background: '#C75B3A' }}
            >
              <Plus className="h-3.5 w-3.5" strokeWidth={2} />
              Ajouter un monument
            </Link>
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
