import { useState, useEffect, useCallback } from 'react';
import { useParams, Link, useSearchParams, useNavigate } from 'react-router';
import {
  ChevronLeft, AlertTriangle, Loader2, FileText, Compass, Trash2,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { DossierChecklist } from '@/components/dossier/DossierChecklist';
import { AttachDocumentDialog } from '@/components/dossier/AttachDocumentDialog';
import { DeleteDossierDocumentDialog, type DeleteScope } from '@/components/dossier/DeleteDossierDocumentDialog';
import { DocumentPreviewDialog } from '@/components/document/DocumentPreviewDialog';
import { AideDetails } from '@/components/aide/AideDetails';
import { useDossierStore } from '@/stores/useDossierStore';
import { useAideStore } from '@/stores/useAideStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { dossierService } from '@/services/dossier.service';
import { documentService } from '@/services/document.service';
import { DOSSIER_STATUS_LABELS } from '@/constants/dossier-steps';
import { ROUTES } from '@/constants/routes';
import { formatCurrency } from '@/lib/format-utils';
import { toast } from 'sonner';
import type { ChecklistItem, Document, AideMatchResult } from '@/types';

const FONT = "'Cormorant Garamond', serif";

export function DossierDetailPage() {
  const { dossierId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const dossier = useDossierStore((s) => s.dossiers.find((d) => d.id === dossierId));
  const addDossier = useDossierStore((s) => s.addDossier);
  const aide = useAideStore((s) => dossier ? s.aides.find((a) => a.id === dossier.aideId) : undefined);
  const diagnosticsByMonument = useAideStore((s) => s.diagnosticsByMonument);
  const monument = useMonumentStore((s) => dossier ? s.monuments.find((m) => m.id === dossier.monumentId) : undefined);

  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [attachingItem, setAttachingItem] = useState<ChecklistItem | null>(null);
  const [busyItemId, setBusyItemId] = useState<string | null>(null);
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null);
  const [deletingItem, setDeletingItem] = useState<ChecklistItem | null>(null);
  const [deleting, setDeleting] = useState(false);
  const documents = useDocumentStore((s) => s.documents);
  const fetchDocuments = useDocumentStore((s) => s.fetchDocuments);
  const linkToDossierStore = useDocumentStore((s) => s.linkToDossier);
  const unlinkFromDossierStore = useDocumentStore((s) => s.unlinkFromDossier);
  const deleteDocumentStore = useDocumentStore((s) => s.deleteDocument);

  const activeTab = searchParams.get('tab') === 'aide' ? 'aide' : 'dossier';
  const handleTabChange = useCallback((value: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('tab', value);
      return next;
    }, { replace: true });
  }, [setSearchParams]);

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

  const matchResult: AideMatchResult | null = (() => {
    if (!aide) return null;
    const diagnostic = diagnosticsByMonument[dossier.monumentId];
    if (!diagnostic) return null;
    return diagnostic.aidesEligibles.find((m) => m.aide.id === aide.id)
      ?? diagnostic.aidesPotentiellementEligibles.find((m) => m.aide.id === aide.id)
      ?? diagnostic.aidesNonEligibles.find((m) => m.aide.id === aide.id)
      ?? null;
  })();

  const handleAttach = async (document: Document) => {
    if (!attachingItem) return;
    const itemId = attachingItem.id;
    setBusyItemId(itemId);
    try {
      if (!document.dossiersUtilises.includes(dossier.id)) {
        await linkToDossierStore(document.id, dossier.id);
      }
      await dossierService.updateChecklistItem(dossier.id, itemId, 'fourni', document.id);
      toast.success('Document rattaché');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors du rattachement');
      throw err;
    } finally {
      setBusyItemId(null);
    }
  };

  const handleDelete = async (scope: DeleteScope) => {
    if (!deletingItem?.documentId) return;
    const documentId = deletingItem.documentId;
    const itemId = deletingItem.id;
    setBusyItemId(itemId);

    const ignoreMissing = async (fn: () => Promise<unknown>) => {
      try {
        await fn();
      } catch (err) {
        const msg = err instanceof Error ? err.message.toLowerCase() : '';
        const isMissing =
          msg.includes('404') ||
          msg.includes('not found') ||
          msg.includes('introuvable') ||
          msg.includes('non trouvé') ||
          msg.includes('failed to fetch');
        if (!isMissing) throw err;
      }
    };

    try {
      await ignoreMissing(() => unlinkFromDossierStore(documentId, dossier.id));
      if (scope === 'everywhere') {
        await ignoreMissing(() => deleteDocumentStore(documentId));
      }
      await dossierService.updateChecklistItem(dossier.id, itemId, 'manquant');
      toast.success(
        scope === 'everywhere'
          ? 'Document supprimé définitivement'
          : 'Document retiré du dossier',
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors de la suppression');
      throw err;
    } finally {
      setBusyItemId(null);
    }
  };

  const handlePreview = async (documentId: string) => {
    const existing = documents.find((d) => d.id === documentId);
    if (existing) {
      setPreviewDoc(existing);
      return;
    }
    try {
      const doc = await documentService.getById(documentId);
      setPreviewDoc(doc);
      fetchDocuments().catch(() => {});
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Document introuvable');
    }
  };

  const handleDeleteDossier = async () => {
    if (!dossier || !confirm(`Supprimer ce dossier ? Cette action est irréversible.`)) return;
    setDeleting(true);
    try {
      await dossierService.delete(dossier.id);
      toast.success('Dossier supprimé');
      navigate(ROUTES.DOSSIERS);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors de la suppression');
    } finally {
      setDeleting(false);
    }
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
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
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
            <Link to={ROUTES.MONUMENT_DETAIL(monument.id)} className="inline-flex items-center justify-center h-9 px-4 text-[13px] font-medium border border-[#E4E2DC] rounded-lg text-[#5C6178] hover:bg-[#F8F7F4] transition-colors whitespace-nowrap">
              Voir le monument
            </Link>
          )}
          <button
            onClick={handleDeleteDossier}
            disabled={deleting}
            className="flex items-center justify-center h-9 w-9 border border-[#E4E2DC] rounded-lg text-[#8E92A4] hover:text-red-600 hover:border-red-200 transition-colors flex-shrink-0"
          >
            {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
          </button>
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

      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList>
          <TabsTrigger value="dossier" className="gap-1.5">
            <FileText className="h-4 w-4" />
            Dossier
          </TabsTrigger>
          <TabsTrigger value="aide" className="gap-1.5">
            <Compass className="h-4 w-4" />
            Informations
          </TabsTrigger>
        </TabsList>

        <TabsContent value="dossier" className="mt-4 space-y-6">
          <Panel title="Pièces du dossier">
            <DossierChecklist
              items={dossier.checklist}
              onRequestAttach={(item) => setAttachingItem(item)}
              onPreview={handlePreview}
              onRequestDelete={(item) => setDeletingItem(item)}
              busyItemId={busyItemId}
              readOnly={dossier.statut === 'soumis'}
            />
          </Panel>

          {dossier.statut !== 'soumis' && (
            <div className="flex items-start gap-3 p-4 rounded-xl border border-amber-200 bg-amber-50">
              <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
              <div className="text-[13px]">
                <p className="font-semibold text-amber-800">Dépôt manuel obligatoire</p>
                <p className="text-amber-700 mt-0.5">Patrys vous aide à préparer votre dossier, mais le dépôt auprès de l'organisme doit être effectué par vos soins.</p>
              </div>
            </div>
          )}

          {dossier.montantEstime && (
            <div className="text-[13px] text-[#8E92A4]">
              Montant estimé des travaux : <span className="font-semibold text-[#1B1E2E]">{formatCurrency(dossier.montantEstime)}</span>
            </div>
          )}
        </TabsContent>

        <TabsContent value="aide" className="mt-4">
          {aide ? (
            <AideDetails aide={aide} matchResult={matchResult} monumentName={monument?.nom} />
          ) : (
            <EmptyState
              icon={Compass}
              title="Aide introuvable"
              description="Les informations de l'aide liée à ce dossier sont indisponibles."
            />
          )}
        </TabsContent>
      </Tabs>

      <AttachDocumentDialog
        open={!!attachingItem}
        onOpenChange={(open) => { if (!open) setAttachingItem(null); }}
        monumentId={dossier.monumentId}
        defaultName={attachingItem?.label}
        onAttach={handleAttach}
      />

      <DocumentPreviewDialog
        document={previewDoc}
        open={!!previewDoc}
        onOpenChange={(open) => { if (!open) setPreviewDoc(null); }}
      />

      <DeleteDossierDocumentDialog
        open={!!deletingItem}
        onOpenChange={(open) => { if (!open) setDeletingItem(null); }}
        itemLabel={deletingItem?.label}
        onConfirm={handleDelete}
      />
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
