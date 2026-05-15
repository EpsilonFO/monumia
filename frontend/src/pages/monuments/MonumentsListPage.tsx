import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router';
import { Plus, Church, Loader2, Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { MonumentCard } from '@/components/monument/MonumentCard';
import { useMonuments } from '@/hooks/useActiveMonument';
import { useAideStore } from '@/stores/useAideStore';
import { aideService } from '@/services/aide.service';

type MonumentSortKey = 'recent' | 'oldest' | 'name' | 'modified';

export function MonumentsListPage() {
  const { monuments, loading } = useMonuments();
  const diagnosticsByMonument = useAideStore((s) => s.diagnosticsByMonument);
  const setDiagnostic = useAideStore((s) => s.setDiagnostic);
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<MonumentSortKey>('recent');

  useEffect(() => {
    for (const m of monuments) {
      if (!diagnosticsByMonument[m.id]) {
        aideService.getDiagnostics(m.id).then((diagnostics) => {
          if (diagnostics.length > 0) setDiagnostic(m.id, diagnostics[0]);
        }).catch(console.error);
      }
    }
  }, [monuments]);

  const visibleMonuments = useMemo(() => {
    const q = search.trim().toLowerCase();
    const filtered = q
      ? monuments.filter((m) =>
          m.nom.toLowerCase().includes(q) ||
          (m.commune?.toLowerCase().includes(q) ?? false)
        )
      : monuments;

    const sorted = [...filtered];
    switch (sortKey) {
      case 'recent':
        sorted.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
        break;
      case 'oldest':
        sorted.sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime());
        break;
      case 'name':
        sorted.sort((a, b) => a.nom.localeCompare(b.nom, 'fr', { sensitivity: 'base' }));
        break;
      case 'modified':
        sorted.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
        break;
    }
    return sorted;
  }, [monuments, search, sortKey]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mes monuments"
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
        <>
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1 sm:max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#8E92A4]" strokeWidth={1.8} />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Rechercher un monument..."
                className="h-10 pl-9 text-[14px] bg-white border-[#E4E2DC]"
              />
            </div>

            <Select value={sortKey} onValueChange={(v) => setSortKey(v as MonumentSortKey)}>
              <SelectTrigger className="w-full sm:w-56 h-10 text-[14px] bg-white border-[#E4E2DC]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="recent">Ajoutés récemment</SelectItem>
                <SelectItem value="oldest">Plus anciens</SelectItem>
                <SelectItem value="modified">Récemment modifiés</SelectItem>
                <SelectItem value="name">Nom (A → Z)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {visibleMonuments.length === 0 ? (
            <EmptyState
              icon={Church}
              title="Aucun résultat"
              description="Aucun monument ne correspond à votre recherche."
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {visibleMonuments.map((monument) => (
                <MonumentCard key={monument.id} monument={monument} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
