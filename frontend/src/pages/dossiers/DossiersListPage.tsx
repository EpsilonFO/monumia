import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { Church, Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { DossierCard, MONUMENT_COLORS } from '@/components/dossier/DossierCard';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { dossierService } from '@/services/dossier.service';
import { ROUTES } from '@/constants/routes';

type DossierSortKey = 'recent' | 'oldest' | 'name' | 'modified';

export function DossiersListPage() {
  const user = useAuthStore((s) => s.user);
  const monuments = useMonumentStore((s) => s.monuments);
  const dossiers = useDossierStore((s) => s.dossiers);
  const loaded = useDossierStore((s) => s.loaded);
  const [searchParams] = useSearchParams();

  useEffect(() => {
    if (user && !loaded) { dossierService.fetchAll().catch(console.error); }
  }, [user, loaded]);

  const monumentFilterParam = searchParams.get('monument');
  const [selectedMonument, setSelectedMonument] = useState(monumentFilterParam ?? 'all');
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<DossierSortKey>('recent');

  const userMonuments = useMemo(
    () => (user ? monuments.filter((m) => m.userId === user.id) : []),
    [monuments, user],
  );

  // Stable color per monument (index in userMonuments list)
  const monumentColorMap = useMemo(
    () => Object.fromEntries(
      userMonuments.map((m, i) => [m.id, MONUMENT_COLORS[i % MONUMENT_COLORS.length]])
    ),
    [userMonuments],
  );

  const monumentFilter = selectedMonument !== 'all' ? selectedMonument : null;

  const userDossiers = useMemo(() => {
    if (!user) return [];
    let filtered = dossiers;
    if (monumentFilter) filtered = filtered.filter((d) => d.monumentId === monumentFilter);

    const q = search.trim().toLowerCase();
    if (q) {
      const monumentNameById = new Map(monuments.map((m) => [m.id, m.nom.toLowerCase()]));
      filtered = filtered.filter((d) =>
        d.titre.toLowerCase().includes(q) ||
        (monumentNameById.get(d.monumentId) ?? '').includes(q)
      );
    }

    const sorted = [...filtered];
    switch (sortKey) {
      case 'recent':
        sorted.sort((a, b) => new Date(b.dateCreation).getTime() - new Date(a.dateCreation).getTime());
        break;
      case 'oldest':
        sorted.sort((a, b) => new Date(a.dateCreation).getTime() - new Date(b.dateCreation).getTime());
        break;
      case 'name':
        sorted.sort((a, b) => a.titre.localeCompare(b.titre, 'fr', { sensitivity: 'base' }));
        break;
      case 'modified':
        sorted.sort((a, b) => new Date(b.dateDerniereModification).getTime() - new Date(a.dateDerniereModification).getTime());
        break;
    }
    return sorted;
  }, [dossiers, monuments, user, monumentFilter, search, sortKey]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mes dossiers"
        description="Suivez l'avancement de vos demandes de financement"
      />

      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 sm:max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#8E92A4]" strokeWidth={1.8} />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher un dossier..."
            className="h-10 pl-9 text-[14px] bg-white border-[#E4E2DC]"
          />
        </div>

        {userMonuments.length > 1 && (
          <Select value={selectedMonument} onValueChange={setSelectedMonument}>
            <SelectTrigger className="w-full sm:w-56 h-10 text-[14px] bg-white border-[#E4E2DC]">
              <SelectValue placeholder="Tous les monuments" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tous les monuments</SelectItem>
              {userMonuments.map((m, i) => (
                <SelectItem key={m.id} value={m.id}>
                  <span className="flex items-center gap-2">
                    <span
                      className="w-2 h-2 rounded-full shrink-0 inline-block"
                      style={{ background: MONUMENT_COLORS[i % MONUMENT_COLORS.length] }}
                    />
                    {m.nom}
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        <Select value={sortKey} onValueChange={(v) => setSortKey(v as DossierSortKey)}>
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

      {userDossiers.length === 0 ? (
        <EmptyState
          icon={Church}
          title={search.trim() ? 'Aucun résultat' : 'Aucun dossier en cours'}
          description={search.trim()
            ? "Aucun dossier ne correspond à votre recherche."
            : monumentFilter
              ? "Aucun dossier pour ce monument. Lancez un diagnostic depuis la fiche du monument."
              : "Rendez-vous sur l'onglet Monuments pour lancer un diagnostic et créer votre premier dossier."}
          action={
            <Link
              to={ROUTES.MONUMENTS}
              className="inline-flex items-center gap-2 px-5 py-2.5 text-[13px] font-semibold text-white rounded-lg transition-all duration-300 hover:shadow-md"
              style={{ background: '#1A237E' }}
            >
              <Church className="h-3.5 w-3.5" strokeWidth={1.8} />
              Voir mes monuments
            </Link>
          }
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {userDossiers.map((dossier) => (
            <DossierCard
              key={dossier.id}
              dossier={dossier}
              monumentColor={monumentColorMap[dossier.monumentId]}
            />
          ))}
        </div>
      )}
    </div>
  );
}
