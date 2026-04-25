import { useEffect, useMemo, useState } from 'react';
import { useParams, Link, useNavigate, useSearchParams, Navigate } from 'react-router';
import { ChevronLeft, FileText, FolderOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { PageHeader } from '@/components/shared/PageHeader';
import { Disclaimer } from '@/components/shared/Disclaimer';
import { AideDetails } from '@/components/aide/AideDetails';
import { useAideStore } from '@/stores/useAideStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useSegmentLabel } from '@/hooks/useSegment';
import { useAidesAccess } from '@/hooks/useAidesAccess';
import { aideService } from '@/services/aide.service';
import { dossierService } from '@/services/dossier.service';
import { ROUTES } from '@/constants/routes';
import { toast } from 'sonner';
import type { Aide, AideMatchResult } from '@/types';

export function AideDetailPage() {
  const { locked } = useAidesAccess();
  if (locked) {
    return <Navigate to="/tarifs" replace />;
  }
  const { aideId } = useParams();
  const [searchParams] = useSearchParams();
  const monumentId = searchParams.get('monumentId');
  const navigate = useNavigate();

  const storeAide = useAideStore((s) => s.aides.find((a) => a.id === aideId));
  const diagnosticsByMonument = useAideStore((s) => s.diagnosticsByMonument);
  const user = useAuthStore((s) => s.user);
  const monument = useMonumentStore((s) =>
    monumentId ? s.monuments.find((m) => m.id === monumentId) : undefined
  );
  const dossiers = useDossierStore((s) => s.dossiers);
  useSegmentLabel();

  const [fetchedAide, setFetchedAide] = useState<Aide | null>(null);
  useEffect(() => {
    if (!storeAide && aideId) {
      aideService.getById(aideId).then(setFetchedAide).catch(console.error);
    }
  }, [storeAide, aideId]);


  const aide = storeAide ?? fetchedAide;

  const matchResult = useMemo((): AideMatchResult | null => {
    if (!aide || !monumentId) return null;
    const diagnostic = diagnosticsByMonument[monumentId];
    if (!diagnostic) return null;
    return diagnostic.aidesEligibles.find((m) => m.aide.id === aide.id)
      ?? diagnostic.aidesPotentiellementEligibles.find((m) => m.aide.id === aide.id)
      ?? diagnostic.aidesNonEligibles.find((m) => m.aide.id === aide.id)
      ?? null;
  }, [aide, monumentId, diagnosticsByMonument]);

  const existingDossier = useMemo(() => {
    if (!aide || !monumentId) return null;
    return dossiers.find((d) => d.monumentId === monumentId && d.aideId === aide.id) ?? null;
  }, [aide, monumentId, dossiers]);

  const [creating, setCreating] = useState(false);

  if (!aide) {
    return (
      <div className="space-y-4">
        <PageHeader title="Aide introuvable" />
        <p className="text-muted-foreground">Cette aide n'existe pas.</p>
        <Button asChild variant="outline">
          <Link to={ROUTES.MONUMENTS}>
            <ChevronLeft className="h-4 w-4 mr-1" />
            Retour aux monuments
          </Link>
        </Button>
      </div>
    );
  }

  const handleCreateDossier = async () => {
    if (!monument || !user || creating) return;
    if (existingDossier) {
      navigate(ROUTES.DOSSIER_DETAIL(existingDossier.id));
      return;
    }
    setCreating(true);
    try {
      const dossier = await dossierService.create(
        monument.id,
        aide.id,
        monument.travauxEnvisages ?? []
      );
      toast.success('Dossier créé');
      navigate(ROUTES.DOSSIER_DETAIL(dossier.id));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors de la création du dossier');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground flex-wrap">
        <Link to={ROUTES.MONUMENTS} className="hover:text-foreground transition-colors">
          Monuments
        </Link>
        {monument && (
          <>
            <span>/</span>
            <Link
              to={`${ROUTES.MONUMENT_DETAIL(monument.id)}?tab=aides`}
              className="hover:text-foreground transition-colors truncate max-w-[200px]"
            >
              {monument.nom}
            </Link>
          </>
        )}
        <span>/</span>
        <span className="text-foreground truncate">{aide.nomCourt}</span>
      </div>

      {!monument && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          <p className="font-semibold mb-1">Contexte monument manquant</p>
          <p>
            Pour évaluer l'éligibilité à cette aide et créer un dossier, ouvrez-la depuis l'onglet
            « Aides » d'un monument.
          </p>
          <Button asChild variant="outline" size="sm" className="mt-3">
            <Link to={ROUTES.MONUMENTS}>Voir mes monuments</Link>
          </Button>
        </div>
      )}

      {monument && matchResult?.eligible && (
        <div className="flex justify-end">
          <Button onClick={handleCreateDossier} disabled={creating}>
            {existingDossier ? (
              <>
                <FolderOpen className="h-4 w-4 mr-2" />
                Ouvrir le dossier existant
              </>
            ) : (
              <>
                <FileText className="h-4 w-4 mr-2" />
                {creating ? 'Création...' : 'Créer un dossier'}
              </>
            )}
          </Button>
        </div>
      )}

      <AideDetails aide={aide} matchResult={matchResult} monumentName={monument?.nom} />

      <Disclaimer />
    </div>
  );
}
