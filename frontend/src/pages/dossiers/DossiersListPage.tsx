import { useMemo } from 'react';
import { Link, useSearchParams } from 'react-router';
import { LayoutGrid, List, FileText, Landmark } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { DossierPipeline } from '@/components/dossier/DossierPipeline';
import { DossierCard } from '@/components/dossier/DossierCard';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { ROUTES } from '@/constants/routes';

export function DossiersListPage() {
  const user = useAuthStore((s) => s.user);
  const monuments = useMonumentStore((s) => s.monuments);
  const dossiers = useDossierStore((s) => s.dossiers);
  const [searchParams] = useSearchParams();

  const monumentFilter = searchParams.get('monument');

  const userDossiers = useMemo(() => {
    if (!user) return [];
    let filtered = dossiers.filter((d) => d.userId === user.id);
    if (monumentFilter) {
      filtered = filtered.filter((d) => d.monumentId === monumentFilter);
    }
    return filtered;
  }, [dossiers, user, monumentFilter]);

  const filterMonument = useMemo(
    () => monumentFilter ? monuments.find((m) => m.id === monumentFilter) : undefined,
    [monuments, monumentFilter]
  );

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

      {userDossiers.length === 0 ? (
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
        <div className="space-y-4">
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
      )}
    </div>
  );
}
