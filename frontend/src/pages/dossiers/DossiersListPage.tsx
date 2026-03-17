import { useEffect, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router';
import { FileText, Landmark } from 'lucide-react';
import { Button } from '@/components/ui/button';
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
    if (user && !loaded) {
      dossierService.fetchAll().catch(console.error);
    }
  }, [user, loaded]);

  const monumentFilter = searchParams.get('monument');

  const userDossiers = useMemo(() => {
    if (!user) return [];
    let filtered = dossiers;
    if (monumentFilter) {
      filtered = filtered.filter((d) => d.monumentId === monumentFilter);
    }
    return filtered;
  }, [dossiers, user, monumentFilter]);

  const filterMonument = useMemo(
    () => monumentFilter ? monuments.find((m) => m.id === monumentFilter) : undefined,
    [monuments, monumentFilter]
  );

  const hasDossiers = userDossiers.length > 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mes dossiers"
        description={
          filterMonument
            ? `Dossiers pour ${filterMonument.nom}`
            : "Suivez l'avancement de vos demandes de financement"
        }
        action={
          monumentFilter ? (
            <Button asChild variant="outline">
              <Link to={ROUTES.DOSSIERS}>
                Voir tous les dossiers
              </Link>
            </Button>
          ) : undefined
        }
      />

      {!hasDossiers ? (
        <EmptyState
          icon={FileText}
          title="Aucun dossier en cours actuellement"
          description={
            monumentFilter
              ? "Aucun dossier pour ce monument. Lancez un diagnostic depuis la fiche du monument pour identifier les aides disponibles."
              : "Rendez-vous sur l'onglet Monuments pour lancer un diagnostic et créer votre premier dossier."
          }
          action={
            <Button asChild>
              <Link to={ROUTES.MONUMENTS}>
                <Landmark className="h-4 w-4 mr-2" />
                Voir mes monuments
              </Link>
            </Button>
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
