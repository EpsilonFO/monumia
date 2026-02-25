import { useMemo } from 'react';
import { Link } from 'react-router';
import { LayoutGrid, List, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { DossierPipeline } from '@/components/dossier/DossierPipeline';
import { DossierCard } from '@/components/dossier/DossierCard';
import { useAuthStore } from '@/stores/useAuthStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { ROUTES } from '@/constants/routes';

export function DossiersListPage() {
  const user = useAuthStore((s) => s.user);
  const dossiers = useDossierStore((s) => s.dossiers);

  const userDossiers = useMemo(
    () => (user ? dossiers.filter((d) => d.userId === user.id) : []),
    [dossiers, user]
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mes dossiers"
        description="Suivez l'avancement de vos demandes de financement"
        action={
          <Button asChild>
            <Link to={ROUTES.AIDES}>
              Lancer un diagnostic
            </Link>
          </Button>
        }
      />

      {userDossiers.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="Aucun dossier en cours"
          description="Lancez un diagnostic d'aides pour identifier les financements disponibles et créer votre premier dossier."
          action={
            <Button asChild>
              <Link to={ROUTES.AIDES}>Diagnostic d'aides</Link>
            </Button>
          }
        />
      ) : (
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
      )}
    </div>
  );
}
