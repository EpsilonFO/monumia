import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router';
import { ChevronLeft, FileText, Loader2, AlertTriangle, Trash2, BookOpen } from 'lucide-react';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { EmptyState } from '@/components/shared/EmptyState';
import { AideDetails } from '@/components/aide/AideDetails';
import { AideStatutSelect } from '@/components/aide/AideStatutSelect';
import { DossierChecklist } from '@/components/dossier/DossierChecklist';
import { AttachDocumentDialog } from '@/components/dossier/AttachDocumentDialog';
import { DocumentPreviewDialog } from '@/components/document/DocumentPreviewDialog';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { useTemplateStore } from '@/stores/useTemplateStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { useSuiviStore } from '@/stores/useSuiviStore';
import { matchTemplates } from '@/lib/template-matching';
import { projectPermissions } from '@/lib/project-permissions';
import { monumentService } from '@/services/monument.service';
import { aideService } from '@/services/aide.service';
import { dossierService } from '@/services/dossier.service';
import { documentService } from '@/services/document.service';
import { suiviService } from '@/services/suivi.service';
import { C, SERIF } from '@/lib/brand';
import { ROUTES } from '@/constants/routes';
import { toast } from 'sonner';
import type { Aide, ChecklistItem, Document } from '@/types';

export function DossierDetailPage() {
  const { projetId, dossierId } = useParams();
  const navigate = useNavigate();

  const monument = useMonumentStore((s) => s.monuments.find((m) => m.id === projetId));
  const addMonument = useMonumentStore((s) => s.addMonument);

  const dossier = useDossierStore((s) => s.dossiers.find((d) => d.id === dossierId));
  const dossierLoaded = useDossierStore((s) => s.loaded);
  const setDossiers = useDossierStore((s) => s.setDossiers);

  const templates = useTemplateStore((s) => s.templates);
  const templatesLoaded = useTemplateStore((s) => s.loaded);
  const fetchTemplates = useTemplateStore((s) => s.fetchAll);

  const documents = useDocumentStore((s) => s.documents);
  const fetchDocuments = useDocumentStore((s) => s.fetchDocuments);
  const linkToDossierStore = useDocumentStore((s) => s.linkToDossier);
  const unlinkFromDossierStore = useDocumentStore((s) => s.unlinkFromDossier);
  const addToProjectsStore = useDocumentStore((s) => s.addToProjects);

  const currentUserId = useAuthStore((s) => s.user?.id);

  // Avancement (statut / montant obtenu / motif de refus) du dossier. Le suivi est
  // indexé par (monument, aide) ; il vit là où un dossier existe — donc ici.
  const allSuivis = useSuiviStore((s) => s.suivis);
  const suiviLoaded = useSuiviStore((s) => (projetId ? s.loadedMonuments[projetId] : false));
  const suivi = useMemo(
    () => allSuivis.find((s) => s.monumentId === projetId && s.aideId === dossier?.aideId),
    [allSuivis, projetId, dossier?.aideId],
  );

  const [aide, setAide] = useState<Aide | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [attachingItem, setAttachingItem] = useState<ChecklistItem | null>(null);
  const [busyItemId, setBusyItemId] = useState<string | null>(null);
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const monumentFetchedRef = useRef(false);

  useEffect(() => {
    if (monument || !projetId || monumentFetchedRef.current) return;
    monumentFetchedRef.current = true;
    monumentService.getById(projetId).then(addMonument).catch(() => setNotFound(true));
  }, [monument, projetId, addMonument]);

  // Rafraîchir les dossiers au montage (deep link + freshness inter-comptes).
  useEffect(() => {
    dossierService.fetchAll().then(setDossiers).catch(console.error);
  }, [setDossiers]);

  useEffect(() => {
    if (dossierLoaded && !dossier) setNotFound(true);
  }, [dossierLoaded, dossier]);

  useEffect(() => { fetchDocuments().catch(() => {}); }, [fetchDocuments]);
  useEffect(() => { if (!templatesLoaded) fetchTemplates().catch(() => {}); }, [templatesLoaded, fetchTemplates]);
  useEffect(() => { if (projetId && !suiviLoaded) suiviService.fetchByMonument(projetId).catch(console.error); }, [projetId, suiviLoaded]);

  // Charge l'aide (pour rapprocher les modèles de la bibliothèque des pièces).
  useEffect(() => {
    if (!dossier?.aideId) return;
    aideService.getById(dossier.aideId).then(setAide).catch(() => {});
  }, [dossier?.aideId]);

  const templatesByItemId = useMemo(() => {
    if (!dossier || templates.length === 0) return {};
    const map: Record<string, typeof templates> = {};
    for (const item of dossier.checklist) {
      const matches = matchTemplates(templates, item.label, aide?.categorie);
      if (matches.length > 0) map[item.id] = matches;
    }
    return map;
  }, [dossier, templates, aide?.categorie]);

  const handleAttach = async (document: Document) => {
    if (!attachingItem || !dossier || !monument) return;
    const itemId = attachingItem.id;
    setBusyItemId(itemId);
    try {
      // Rattacher une pièce au dossier l'associe aussi au projet : le document
      // apparaît dans l'onglet « Documents » du projet pour toute l'équipe.
      if (!document.monumentIds.includes(monument.id)) {
        await addToProjectsStore(document.id, [monument.id]);
      }
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

  const handleDeleteItem = async (item: ChecklistItem) => {
    if (!item.documentId || !dossier) return;
    const documentId = item.documentId;
    setBusyItemId(item.id);
    try {
      try { await unlinkFromDossierStore(documentId, dossier.id); }
      catch (err) {
        const msg = err instanceof Error ? err.message.toLowerCase() : '';
        const isMissing = msg.includes('404') || msg.includes('not found') || msg.includes('introuvable') || msg.includes('non trouvé') || msg.includes('failed to fetch');
        if (!isMissing) throw err;
      }
      await dossierService.updateChecklistItem(dossier.id, item.id, 'manquant');
      toast.success('Document retiré du dossier');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors de la suppression');
    } finally {
      setBusyItemId(null);
    }
  };

  // Remplacer / supprimer une pièce : l'auteur du document, OU un chef de projet /
  // adjoint (tous les droits sur les docs). Un collaborateur ne peut agir que sur
  // les siens. Consultation ouverte à tous.
  const canManageAnyDoc = projectPermissions(monument?.myRole ?? null).canDeleteAnyDoc;
  const canModifyItem = useCallback(
    (item: ChecklistItem) =>
      !!item.documentId &&
      (canManageAnyDoc ||
        documents.some((d) => d.id === item.documentId && d.userId === currentUserId)),
    [documents, currentUserId, canManageAnyDoc],
  );

  const canManageDossier = projectPermissions(monument?.myRole ?? null).canEditProject;

  const handleDeleteDossier = async () => {
    if (!dossier || !projetId) return;
    setDeleting(true);
    try {
      await dossierService.delete(dossier.id);
      toast.success('Dossier supprimé — l’aide redevient disponible');
      navigate(`${ROUTES.PROJET_DETAIL(projetId)}?tab=dossiers`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors de la suppression du dossier');
      setDeleting(false);
    }
  };

  const handlePreview = async (documentId: string) => {
    const existing = documents.find((d) => d.id === documentId);
    if (existing) { setPreviewDoc(existing); return; }
    try {
      const doc = await documentService.getById(documentId);
      setPreviewDoc(doc);
      fetchDocuments().catch(() => {});
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Document introuvable');
    }
  };

  if (notFound) {
    return (
      <div className="space-y-4">
        <h1 className="text-[20px]" style={{ fontFamily: SERIF, color: C.ink }}>Dossier introuvable</h1>
        <Link to={projetId ? ROUTES.PROJET_DETAIL(projetId) : ROUTES.PROJETS} className="inline-flex items-center gap-1.5 text-[13px] font-medium" style={{ color: C.blue }}>
          <ChevronLeft className="h-3.5 w-3.5" /> Retour au projet
        </Link>
      </div>
    );
  }

  if (!dossier || !monument) return <div className="flex justify-center py-12"><Loader2 className="h-5 w-5 animate-spin" style={{ color: C.blueLight }} /></div>;

  const [aideName] = dossier.titre.split(' — ');

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-[13px]" style={{ color: '#6a7180' }}>
        <Link to={ROUTES.PROJETS} className="hover:opacity-70 transition-opacity">Projets</Link>
        <span>/</span>
        <Link to={`${ROUTES.PROJET_DETAIL(monument.id)}?tab=dossiers`} className="hover:opacity-70 transition-opacity">{monument.nom}</Link>
        <span>/</span>
        <span className="truncate" style={{ color: C.ink }}>{aideName}</span>
      </div>

      <h1 className="text-[clamp(1.4rem,3vw,1.9rem)] leading-tight" style={{ fontFamily: SERIF, color: C.ink }}>{dossier.titre}</h1>

      {projetId && dossier.aideId && (
        <AideStatutSelect monumentId={projetId} aideId={dossier.aideId} suivi={suivi} />
      )}

      <div className="space-y-6">
        <div className="rounded-2xl border overflow-hidden" style={{ background: C.card, borderColor: C.border }}>
          <div className="px-5 py-3 border-b" style={{ borderColor: C.border }}>
            <h3 className="text-[16px]" style={{ fontFamily: SERIF, color: C.ink }}>Pièces du dossier</h3>
          </div>
          <div className="px-5 py-4">
            {dossier.checklist.length === 0 ? (
              <EmptyState icon={FileText} title="Aucune pièce" description="Ce dossier ne comporte aucune pièce à fournir." />
            ) : (
              <DossierChecklist
                items={dossier.checklist}
                templatesByItemId={templatesByItemId}
                onRequestAttach={(item) => setAttachingItem(item)}
                onPreview={handlePreview}
                onRequestDelete={handleDeleteItem}
                canModifyItem={canModifyItem}
                busyItemId={busyItemId}
                readOnly={dossier.statut === 'soumis'}
              />
            )}
          </div>
        </div>

        <div className="flex items-start gap-3 p-4 rounded-xl border" style={{ borderColor: C.orangeVif, background: C.paleOrange }}>
          <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" style={{ color: C.orange }} />
          <div className="text-[13px]">
            <p className="font-semibold" style={{ color: C.ink }}>Dépôt manuel obligatoire</p>
            <p className="mt-0.5" style={{ color: '#6a7180' }}>Monumia vous aide à préparer votre dossier, mais le dépôt auprès de l'organisme doit être effectué par vos soins.</p>
          </div>
        </div>

        {aide && (
          <div className="space-y-3 pt-2">
            <h3 className="flex items-center gap-2 text-[16px]" style={{ fontFamily: SERIF, color: C.ink }}>
              <BookOpen className="h-4 w-4" style={{ color: C.blue }} />À propos de l'aide
            </h3>
            <AideDetails
              aide={aide}
              monumentName={monument.nom}
              showHeader={false}
              showDocumentsRequis={false}
              aside={canManageDossier ? (
                <button
                  onClick={() => setConfirmDeleteOpen(true)}
                  disabled={deleting}
                  className="inline-flex w-full items-center justify-center gap-2 px-4 py-2 text-[13px] font-semibold rounded-lg border transition-colors hover:bg-[#fdf2f1] disabled:opacity-60"
                  style={{ color: '#c0271d', borderColor: '#e7c3bf' }}
                >
                  {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" strokeWidth={1.8} />}
                  Supprimer le dossier
                </button>
              ) : undefined}
            />
          </div>
        )}
      </div>

      <AlertDialog open={confirmDeleteOpen} onOpenChange={setConfirmDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer ce dossier ?</AlertDialogTitle>
            <AlertDialogDescription>
              Le dossier et ses pièces rattachées seront retirés. L'aide redeviendra disponible dans l'onglet « Aides ». Cette action est irréversible.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Annuler</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={handleDeleteDossier} disabled={deleting}>
              {deleting ? 'Suppression…' : 'Supprimer'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AttachDocumentDialog
        open={!!attachingItem}
        onOpenChange={(open) => { if (!open) setAttachingItem(null); }}
        monumentId={monument.id}
        defaultName={attachingItem?.label}
        onAttach={handleAttach}
      />

      <DocumentPreviewDialog
        document={previewDoc}
        open={!!previewDoc}
        onOpenChange={(open) => { if (!open) setPreviewDoc(null); }}
      />
    </div>
  );
}
