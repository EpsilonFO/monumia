import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router';
import {
  ChevronLeft, AlertTriangle, Loader2,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { PageHeader } from '@/components/shared/PageHeader';
import { DossierChecklist } from '@/components/dossier/DossierChecklist';
import { useDossierStore } from '@/stores/useDossierStore';
import { useAideStore } from '@/stores/useAideStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { dossierService } from '@/services/dossier.service';
import { DOSSIER_STATUS_LABELS } from '@/constants/dossier-steps';
import { ROUTES } from '@/constants/routes';
import { formatCurrency } from '@/lib/format-utils';
import type { ChecklistItemStatus } from '@/types';

const FONT = "'Cormorant Garamond', serif";

export function DossierDetailPage() {
  const { dossierId } = useParams();
  const dossier = useDossierStore((s) => s.dossiers.find((d) => d.id === dossierId));
  const addDossier = useDossierStore((s) => s.addDossier);
  const aide = useAideStore((s) => dossier ? s.aides.find((a) => a.id === dossier.aideId) : undefined);
  const monument = useMonumentStore((s) => dossier ? s.monuments.find((m) => m.id === dossier.monumentId) : undefined);

  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!dossier && dossierId && !loading && !notFound) {
      setLoading(true);
      dossierService.getById(dossierId)
        .then((d) => addDossier(d))
        .catch(() => setNotFound(true))
        .finally(() => setLoading(false));
    }
  }, [dossier, dossierId]);

  if (loading) return <div className="flex justify-center py-12"><Loader2 className="h-5 w-5 animate-spin text-[#8E92A4]" /></div>;

  if (!dossier || notFound) {
    return (
      <div className="space-y-4">
        <PageHeader title="Dossier introuvable" />
        <p className="text-[14px] text-[#8E92A4]">Ce dossier n'existe pas ou a été supprimé.</p>
        <Link to={ROUTES.DOSSIERS} className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[#1A237E] hover:opacity-70 transition-opacity">
          <ChevronLeft className="h-3.5 w-3.5" /> Retour aux dossiers
        </Link>
      </div>
    );
  }

  const statusConfig = DOSSIER_STATUS_LABELS[dossier.statut];

  const handleChecklistChange = (itemId: string, statut: ChecklistItemStatus) => {
    dossierService.updateChecklistItem(dossier.id, itemId, statut).catch(console.error);
  };

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-[13px] text-[#8E92A4]">
        <Link to={ROUTES.DOSSIERS} className="hover:text-[#1B1E2E] transition-colors">Dossiers</Link>
        <span>/</span>
        <span className="text-[#1B1E2E] truncate">{dossier.titre}</span>
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge className={statusConfig?.color ?? ''}>{statusConfig?.label ?? dossier.statut}</Badge>
          </div>
          <h1 className="text-[clamp(1.4rem,3vw,1.8rem)] font-light tracking-[-0.02em] text-[#1B1E2E]" style={{ fontFamily: FONT }}>
            {dossier.titre}
          </h1>
          {dossier.description && <p className="text-[14px] text-[#5C6178]">{dossier.description}</p>}
        </div>
        <div className="flex items-center gap-2">
          {monument && (
            <Link to={ROUTES.MONUMENT_DETAIL(monument.id)} className="px-3 py-2 text-[12px] font-medium border border-[#E4E2DC] rounded-lg text-[#5C6178] hover:bg-[#F8F7F4] transition-colors">
              Voir le monument
            </Link>
          )}
          {aide && (
            <Link to={ROUTES.AIDE_DETAIL(aide.id)} className="px-3 py-2 text-[12px] font-medium border border-[#E4E2DC] rounded-lg text-[#5C6178] hover:bg-[#F8F7F4] transition-colors">
              Voir l'aide
            </Link>
          )}
        </div>
      </div>

      {/* Progress */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-[13px]">
          <span className="text-[#8E92A4]">Progression</span>
          <span className="font-semibold text-[#1B1E2E]">{dossier.progressionPourcentage} %</span>
        </div>
        <Progress value={dossier.progressionPourcentage} className="h-2" />
      </div>

      {/* Documents requis */}
      <Panel title="Pièces du dossier">
        <DossierChecklist items={dossier.checklist} onStatusChange={handleChecklistChange} readOnly={dossier.statut === 'soumis'} />
      </Panel>

      {/* Disclaimer */}
      {dossier.statut !== 'soumis' && (
        <div className="flex items-start gap-3 p-4 rounded-xl border border-amber-200 bg-amber-50">
          <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="text-[13px]">
            <p className="font-semibold text-amber-800">Dépôt manuel obligatoire</p>
            <p className="text-amber-700 mt-0.5">PatriAlta vous aide à préparer votre dossier, mais le dépôt auprès de l'organisme doit être effectué par vos soins.</p>
          </div>
        </div>
      )}

      {dossier.montantEstime && (
        <div className="text-[13px] text-[#8E92A4]">
          Montant estimé des travaux : <span className="font-semibold text-[#1B1E2E]">{formatCurrency(dossier.montantEstime)}</span>
        </div>
      )}
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-[#E4E2DC]/80 overflow-hidden">
      <div className="px-5 py-3 border-b border-[#E4E2DC]">
        <h3 className="text-[15px] font-normal text-[#1B1E2E]" style={{ fontFamily: "'Cormorant Garamond', serif" }}>{title}</h3>
      </div>
      <div className="px-5 py-4">{children}</div>
    </div>
  );
}

