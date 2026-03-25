import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { Church } from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { DossierCard } from '@/components/dossier/DossierCard';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { dossierService } from '@/services/dossier.service';
import { ROUTES } from '@/constants/routes';

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

  const userMonuments = useMemo(() => (user ? monuments.filter((m) => m.userId === user.id) : []), [monuments, user]);
  const monumentFilter = selectedMonument !== 'all' ? selectedMonument : null;

  const userDossiers = useMemo(() => {
    if (!user) return [];
    let filtered = dossiers;
    if (monumentFilter) filtered = filtered.filter((d) => d.monumentId === monumentFilter);
    return filtered;
  }, [dossiers, user, monumentFilter]);

  const filterMonument = useMemo(() => monumentFilter ? monuments.find((m) => m.id === monumentFilter) : undefined, [monuments, monumentFilter]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mes dossiers"
        description={filterMonument ? `Dossiers pour ${filterMonument.nom}` : "Suivez l'avancement de vos demandes de financement"}
        action={monumentFilter ? (
          <Link
            to={ROUTES.DOSSIERS}
            className="inline-flex items-center gap-2 px-4 py-2 text-[13px] font-medium border border-[#E4E2DC] rounded-lg text-[#5C6178] transition-all duration-200 hover:bg-[#F8F7F4]"
          >
            Voir tous les dossiers
          </Link>
        ) : undefined}
      />

      {userMonuments.length > 1 && (
        <Select value={selectedMonument} onValueChange={setSelectedMonument}>
          <SelectTrigger className="w-full sm:w-64 h-10 text-[14px] bg-white border-[#E4E2DC]">
            <SelectValue placeholder="Tous les monuments" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous les monuments</SelectItem>
            {userMonuments.map((m) => (<SelectItem key={m.id} value={m.id}>{m.nom}</SelectItem>))}
          </SelectContent>
        </Select>
      )}

      {userDossiers.length === 0 ? (
        <EmptyState
          icon={Church}
          title="Aucun dossier en cours"
          description={monumentFilter
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
        <div className="space-y-3">
          {userDossiers.map((dossier) => (
            <DossierCard key={dossier.id} dossier={dossier} />
          ))}
        </div>
      )}
    </div>
  );
}
