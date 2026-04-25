import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { Church } from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { DossierCard, MONUMENT_COLORS } from '@/components/dossier/DossierCard';
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
    return filtered;
  }, [dossiers, user, monumentFilter]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mes dossiers"
        description="Suivez l'avancement de vos demandes de financement"
      />

      {userMonuments.length > 1 && (
        <Select value={selectedMonument} onValueChange={setSelectedMonument}>
          <SelectTrigger className="w-full sm:w-64 h-10 text-[14px] bg-white border-[#E4E2DC]">
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
