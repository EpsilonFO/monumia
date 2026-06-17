import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, Link } from 'react-router';
import { ChevronLeft, FileText, BookOpen, Clock, Loader2, AlertTriangle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { EmptyState } from '@/components/shared/EmptyState';
import { AideDetails } from '@/components/aide/AideDetails';
import { DossierChecklist } from '@/components/dossier/DossierChecklist';
import { AttachDocumentDialog } from '@/components/dossier/AttachDocumentDialog';
import { DocumentPreviewDialog } from '@/components/document/DocumentPreviewDialog';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useAideStore } from '@/stores/useAideStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { useTemplateStore } from '@/stores/useTemplateStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { matchTemplates } from '@/lib/template-matching';
import { projectPermissions } from '@/lib/project-permissions';
import { monumentService } from '@/services/monument.service';
import { aideService } from '@/services/aide.service';
import { dossierService } from '@/services/dossier.service';
import { documentService } from '@/services/document.service';
import { C, SERIF } from '@/lib/brand';
import { deadlineLabel } from '@/lib/date-utils';
import { ROUTES } from '@/constants/routes';
import { toast } from 'sonner';
import type { Aide, AideMatchResult, ChecklistItem, Document } from '@/types';

type View = 'description' | 'dossier';

export function AideProjectPage() {
  const { projetId, aideId } = useParams();

  const monument = useMonumentStore((s) => s.monuments.find((m) => m.id === projetId));
  const addMonument = useMonumentStore((s) => s.addMonument);
  const diagnosticsByMonument = useAideStore((s) => s.diagnosticsByMonument);

  const dossiers = useDossierStore((s) => s.dossiers);
  const dossierLoaded = useDossierStore((s) => s.loaded);
  const setDossiers = useDossierStore((s) => s.setDossiers);

  const templates = useTemplateStore((s) => s.templates);
  const templatesLoaded = useTemplateStore((s) => s.loaded);
  const fetchTemplates = useTemplateStore((s) => s.fetchAll);

  const documents = useDocumentStore((s) => s.documents);
  const fetchDocuments = useDocumentStore((s) => s.fetchDocuments);
  const linkToDossierStore = useDocumentStore((s) => s.linkToDossier);
  const unlinkFromDossierStore = useDocumentStore((s) => s.unlinkFromDossier);

  const currentUserId = useAuthStore((s) => s.user?.id);

  const [view, setView] = useState<View>('description');
  const [aide, setAide] = useState<Aide | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [dossierId, setDossierId] = useState<string | null>(null);
  const [creatingDossier, setCreatingDossier] = useState(false);

  const [attachingItem, setAttachingItem] = useState<ChecklistItem | null>(null);
  const [busyItemId, setBusyItemId] = useState<string | null>(null);
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null);

  const monumentFetchedRef = useRef(false);

  const dossier = useDossierStore((s) => s.dossiers.find((d) => d.id === dossierId));

  const diagnostic = projetId ? diagnosticsByMonument[projetId] ?? null : null;
  const matchResult: AideMatchResult | null = useMemo(() => {
    if (!diagnostic || !aideId) return null;
    return diagnostic.aidesEligibles.find((m) => m.aide.id === aideId)
      ?? diagnostic.aidesPotentiellementEligibles.find((m) => m.aide.id === aideId)
      ?? diagnostic.aidesNonEligibles.find((m) => m.aide.id === aideId)
      ?? null;
  }, [diagnostic, aideId]);

  useEffect(() => {
    if (monument || !projetId || monumentFetchedRef.current) return;
    monumentFetchedRef.current = true;
    monumentService.getById(projetId).then(addMonument).catch(() => setNotFound(true));
  }, [monument, projetId, addMonument]);

  useEffect(() => {
    if (!aideId) return;
    const fromDiagnostic = matchResult?.aide;
    if (fromDiagnostic) { setAide(fromDiagnostic); return; }
    aideService.getById(aideId).then(setAide).catch(() => setNotFound(true));
  }, [aideId, matchResult]);

  useEffect(() => {
    if (!dossierLoaded) dossierService.fetchAll().then(setDossiers).catch(console.error);
  }, [dossierLoaded, setDossiers]);

  useEffect(() => { fetchDocuments().catch(() => {}); }, [fetchDocuments]);

  useEffect(() => { if (!templatesLoaded) fetchTemplates().catch(() => {}); }, [templatesLoaded, fetchTemplates]);

  // Modèles de la bibliothèque rapprochés de chaque pièce du dossier (par
  // mots-clés + catégorie de l'aide). Les pièces sans correspondance → pas de
  // modèle proposé.
  const templatesByItemId = useMemo(() => {
    if (!dossier || templates.length === 0) return {};
    const map: Record<string, typeof templates> = {};
    for (const item of dossier.checklist) {
      const matches = matchTemplates(templates, item.label, aide?.categorie);
      if (matches.length > 0) map[item.id] = matches;
    }
    return map;
  }, [dossier, templates, aide?.categorie]);

  const ensureDossier = useCallback(async () => {
    if (!projetId || !aideId || !monument || dossierId || creatingDossier) return;
    // Wait until the dossiers store is hydrated from the server, otherwise the
    // existing-(monument, aide) lookup misses and we create a duplicate dossier
    // (the backend create does not dedupe on monument_id + aide_id).
    if (!dossierLoaded) return;
    const existing = dossiers.find((d) => d.monumentId === projetId && d.aideId === aideId);
    if (existing) { setDossierId(existing.id); return; }
    setCreatingDossier(true);
    try {
      const created = await dossierService.create(projetId, aideId, monument.travauxEnvisages ?? []);
      setDossierId(created.id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors de la création du dossier');
    } finally {
      setCreatingDossier(false);
    }
  }, [projetId, aideId, monument, dossierId, creatingDossier, dossiers, dossierLoaded]);

  // Resolve (or lazily create) the dossier once the user opens the Dossier view
  // AND the store is loaded — retries automatically when fetchAll resolves.
  useEffect(() => {
    if (view === 'dossier') ensureDossier();
  }, [view, ensureDossier]);

  const handleSelectDossier = useCallback(() => {
    setView('dossier');
  }, []);

  const handleAttach = async (document: Document) => {
    if (!attachingItem || !dossier) return;
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

  // Remplacer / supprimer une pièce : réservé à l'auteur du document. La liste
  // `documents` (GET /documents sans filtre) ne contient que MES documents, donc
  // une pièce présente ici = pièce dont je suis l'auteur. Consultation ouverte à tous.
  const canModifyItem = useCallback(
    (item: ChecklistItem) =>
      !!item.documentId &&
      documents.some((d) => d.id === item.documentId && d.userId === currentUserId),
    [documents, currentUserId],
  );

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
        <h1 className="text-[20px]" style={{ fontFamily: SERIF, color: C.ink }}>Aide introuvable</h1>
        <Link to={projetId ? ROUTES.PROJET_DETAIL(projetId) : ROUTES.PROJETS} className="inline-flex items-center gap-1.5 text-[13px] font-medium" style={{ color: C.blue }}>
          <ChevronLeft className="h-3.5 w-3.5" /> Retour au projet
        </Link>
      </div>
    );
  }

  if (!aide || !monument) return <div className="flex justify-center py-12"><Loader2 className="h-5 w-5 animate-spin" style={{ color: C.blueLight }} /></div>;

  const echeance = !aide.permanent && aide.dateLimite ? deadlineLabel(aide.dateLimite) : null;
  // Code couleur unique : < 30 j (ou dépassée) → rouge · 30–100 j → orange · > 100 j → bleu
  const echeanceColor =
    echeance?.urgency === 'urgent' || echeance?.urgency === 'past' ? C.danger
      : echeance?.urgency === 'warning' ? C.orange : C.blue;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-[13px]" style={{ color: '#6a7180' }}>
        <Link to={ROUTES.PROJETS} className="hover:opacity-70 transition-opacity">Projets</Link>
        <span>/</span>
        <Link to={ROUTES.PROJET_DETAIL(monument.id)} className="hover:opacity-70 transition-opacity">{monument.nom}</Link>
        <span>/</span>
        <span className="truncate" style={{ color: C.ink }}>{aide.nomCourt}</span>
      </div>

      <div className="space-y-3">
        <h1 className="text-[clamp(1.4rem,3vw,1.9rem)] leading-tight" style={{ fontFamily: SERIF, color: C.ink }}>{aide.nomCourt}</h1>
        {echeance && (
          <Badge variant="outline" className="gap-1.5" style={{ borderColor: echeanceColor, color: echeanceColor, background: C.card }}>
            <Clock className="h-3 w-3" />
            {echeance.urgency === 'past' ? 'Échéance dépassée' : `Date limite — ${echeance.text}`}
          </Badge>
        )}
      </div>

      {/* Two big segmented buttons */}
      <div className="grid grid-cols-2 gap-2 p-1 rounded-xl border max-w-md" style={{ borderColor: C.border, background: C.cream }}>
        <button
          onClick={() => setView('description')}
          className="flex items-center justify-center gap-2 py-3 rounded-lg text-[14px] font-semibold transition-colors"
          style={view === 'description' ? { background: C.blue, color: '#fff' } : { color: C.ink }}
        >
          <BookOpen className="h-4 w-4" />Description
        </button>
        <button
          onClick={handleSelectDossier}
          className="flex items-center justify-center gap-2 py-3 rounded-lg text-[14px] font-semibold transition-colors"
          style={view === 'dossier' ? { background: C.orange, color: '#fff' } : { color: C.ink }}
        >
          <FileText className="h-4 w-4" />Dossier à remplir
        </button>
      </div>

      {view === 'description' ? (
        <AideDetails aide={aide} matchResult={matchResult} monumentName={monument.nom} />
      ) : creatingDossier || !dossier ? (
        <div className="flex justify-center py-12"><Loader2 className="h-5 w-5 animate-spin" style={{ color: C.blueLight }} /></div>
      ) : (
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
                  readOnly={
                    dossier.statut === 'soumis' ||
                    !projectPermissions(monument.myRole ?? null).canEditProject
                  }
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
        </div>
      )}

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
