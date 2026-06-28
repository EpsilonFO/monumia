import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router';
import { Upload, Search, FolderOpen, Trash2, ChevronDown, ChevronRight, FileStack } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { EmptyState } from '@/components/shared/EmptyState';
import { RoleBadge } from '@/components/sharing/RoleBadge';
import { DocumentTile } from '@/components/document/DocumentTile';
import { ProjectLegend, type LegendItem } from '@/components/document/ProjectLegend';
import { DocumentPreviewDialog } from '@/components/document/DocumentPreviewDialog';
import { UploadDocumentDialog } from '@/components/document/UploadDocumentDialog';
import { ManageDocumentAccessDialog } from '@/components/document/ManageDocumentAccessDialog';
import { AddToProjectDialog } from '@/components/document/AddToProjectDialog';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { C, SERIF } from '@/lib/brand';
import { projectColor } from '@/lib/project-color';
import { groupDocumentsByProject } from '@/lib/group-documents';
import { typeLabel } from '@/lib/document-type-meta';
import { ROUTES } from '@/constants/routes';
import type { Document } from '@/types';
import { toast } from 'sonner';

export function DocumentsPage() {
  const {
    documents, trashedDocuments, loading,
    fetchDocuments, fetchTrashed, trashDocument, restoreDocument, removeFromProject, deleteDocument, updateDocument,
  } = useDocumentStore();
  const monuments = useMonumentStore((s) => s.monuments);
  const dossiers = useDossierStore((s) => s.dossiers);

  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState('all');
  const [activeProject, setActiveProject] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [accessDoc, setAccessDoc] = useState<Document | null>(null);
  const [trashOpen, setTrashOpen] = useState(false);
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null);
  const [addToProjectDoc, setAddToProjectDoc] = useState<Document | null>(null);
  const [renameDoc, setRenameDoc] = useState<Document | null>(null);
  const [renameName, setRenameName] = useState('');
  const [renameLoading, setRenameLoading] = useState(false);

  useEffect(() => {
    fetchDocuments();
    fetchTrashed();
  }, [fetchDocuments, fetchTrashed]);

  // ---- Résolution des noms (depuis les stores, avec repli) ----
  const monumentNames = useMemo(() => {
    const m: Record<string, string> = {};
    monuments.forEach((mo) => { m[mo.id] = mo.nom; });
    return m;
  }, [monuments]);

  const roleByMonument = useMemo(() => {
    const m: Record<string, 'owner' | 'co_owner' | 'member' | null> = {};
    monuments.forEach((mo) => { m[mo.id] = mo.myRole ?? null; });
    return m;
  }, [monuments]);

  const dossiersById = useMemo(() => {
    const m: Record<string, { titre: string; monumentId: string }> = {};
    dossiers.forEach((d) => { m[d.id] = { titre: d.titre, monumentId: d.monumentId }; });
    return m;
  }, [dossiers]);

  const uploaderNames = useMemo(() => {
    const m: Record<string, string> = {};
    monuments.forEach((mo) => {
      (mo.members ?? []).forEach((p) => { m[p.userId] = `${p.prenom} ${p.nom}`.trim(); });
    });
    return m;
  }, [monuments]);

  // ---- Filtrage (recherche + type) ----
  const matches = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (d: Document) => {
      if (filterType !== 'all' && d.type !== filterType) return false;
      if (!q) return true;
      return (
        d.nom.toLowerCase().includes(q) ||
        d.nomFichier.toLowerCase().includes(q) ||
        d.tags.some((t) => t.toLowerCase().includes(q))
      );
    };
  }, [search, filterType]);

  const visibleDocs = useMemo(() => documents.filter(matches), [documents, matches]);
  const { byProject, sansProjet } = useMemo(() => groupDocumentsByProject(visibleDocs), [visibleDocs]);

  const docTypes = useMemo(
    () => Array.from(new Set(documents.map((d) => d.type))).sort(),
    [documents],
  );

  // ---- Sections projet, triées par nom ; légende ----
  // Fix I1: exclude projects whose name is not known (foreign projects the caller
  // is not a member of — they may appear in monument_ids but are not in my store).
  const projectSections = useMemo(() => {
    const entries = Array.from(byProject.entries())
      .filter(([mid]) => monumentNames[mid] !== undefined)
      .map(([mid, docs]) => ({
        mid,
        name: monumentNames[mid]!,
        color: projectColor(mid),
        docs,
      }));
    entries.sort((a, b) => a.name.localeCompare(b.name, 'fr'));
    return entries;
  }, [byProject, monumentNames]);

  const legendItems: LegendItem[] = useMemo(
    () => projectSections.map((s) => ({ id: s.mid, name: s.name, color: s.color, count: s.docs.length })),
    [projectSections],
  );

  const shownSections = activeProject
    ? projectSections.filter((s) => s.mid === activeProject)
    : projectSections;

  // Filet de sécurité : un document que le backend nous a renvoyé (donc visible)
  // mais dont AUCUN projet n'est connu de notre store (projet partagé pas encore
  // chargé, etc.) ne doit jamais disparaître — on l'affiche dans une section à part.
  const orphanDocs = useMemo(
    () =>
      visibleDocs.filter(
        (d) =>
          d.monumentIds.length > 0 &&
          !d.monumentIds.some((mid) => monumentNames[mid] !== undefined),
      ),
    [visibleDocs, monumentNames],
  );

  // ---- Handlers ----
  const handleTrash = async (d: Document) => {
    if (!confirm(`Mettre "${d.nom}" à la corbeille ?`)) return;
    try { await trashDocument(d.id); toast.success('Document mis à la corbeille'); }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Erreur'); }
  };
  const handleRemoveFromProject = async (d: Document, monumentId: string) => {
    try { await removeFromProject(d.id, monumentId); toast.success('Document retiré du projet'); }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Erreur'); }
  };
  const handleRestore = async (d: Document) => {
    try { await restoreDocument(d.id); toast.success('Document restauré'); }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Erreur'); }
  };
  const handleDeletePermanent = async (d: Document) => {
    if (!confirm(`Supprimer définitivement "${d.nom}" ? Cette action est irréversible.`)) return;
    try { await deleteDocument(d.id); toast.success('Document supprimé définitivement'); }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Erreur'); }
  };

  const handleRenameOpen = (d: Document) => {
    setRenameDoc(d);
    setRenameName(d.nom);
  };

  const handleRenameSave = async () => {
    if (!renameDoc) return;
    const trimmed = renameName.trim();
    if (!trimmed || trimmed === renameDoc.nom) { setRenameDoc(null); return; }
    setRenameLoading(true);
    try {
      await updateDocument(renameDoc.id, { nom: trimmed });
      toast.success('Document renommé');
      setRenameDoc(null);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Erreur');
    } finally {
      setRenameLoading(false);
    }
  };

  const tileHandlers = {
    onPreview: setPreviewDoc,
    onAddToProject: (d: Document) => setAddToProjectDoc(d),
    onRename: handleRenameOpen,
    onTrash: handleTrash,
    onRemoveFromProject: handleRemoveFromProject,
    onRestore: handleRestore,
    onDeletePermanent: handleDeletePermanent,
  };

  const totalVisible = visibleDocs.length;
  const isEmpty = documents.length === 0 && trashedDocuments.length === 0;

  return (
    <div className="space-y-6">
      {/* Header (inline, charte) */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl flex items-center justify-center" style={{ background: C.paleBlue }}>
            <FileStack className="h-5 w-5" style={{ color: C.blue }} strokeWidth={1.8} />
          </div>
          <div>
            <h1 className="text-[22px] leading-tight" style={{ fontFamily: SERIF, color: C.ink }}>
              Mes documents
            </h1>
            <p className="text-[13px]" style={{ color: '#6a7180' }}>
              Tous vos fichiers, classés par projet
            </p>
          </div>
        </div>
        <button
          onClick={() => setUploadOpen(true)}
          className="inline-flex items-center gap-2 px-5 py-2.5 text-[13px] font-semibold text-white rounded-lg transition-all duration-200 hover:shadow-md"
          style={{ background: C.orange }}
        >
          <Upload className="h-3.5 w-3.5" strokeWidth={2} />Ajouter un document
        </button>
      </div>

      {/* Légende */}
      <ProjectLegend items={legendItems} activeId={activeProject} onSelect={setActiveProject} />

      {/* Filtres */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: '#8E92A4' }} />
          <Input
            className="pl-9 h-10 text-[14px]"
            style={{ background: C.card, borderColor: C.border }}
            placeholder="Rechercher un document..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select value={filterType} onValueChange={setFilterType}>
          <SelectTrigger className="w-full sm:w-44 h-10 text-[14px]" style={{ background: C.card, borderColor: C.border }}>
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous les types</SelectItem>
            {docTypes.map((t) => (<SelectItem key={t} value={t}>{typeLabel(t)}</SelectItem>))}
          </SelectContent>
        </Select>
      </div>

      {/* Contenu */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-40 rounded-xl animate-pulse" style={{ background: `${C.border}66` }} />
          ))}
        </div>
      ) : isEmpty ? (
        <EmptyState
          icon={FolderOpen}
          title="Aucun document"
          description="Ajoutez vos premiers documents pour les utiliser dans vos projets et dossiers."
          action={
            <button
              onClick={() => setUploadOpen(true)}
              className="inline-flex items-center gap-2 px-5 py-2.5 text-[13px] font-semibold text-white rounded-lg hover:shadow-md transition-all"
              style={{ background: C.orange }}
            >
              <Upload className="h-3.5 w-3.5" strokeWidth={2} />Ajouter un document
            </button>
          }
        />
      ) : (
        <div className="space-y-8">
          {totalVisible === 0 && (search.trim() !== '' || filterType !== 'all') && (
            <p className="text-[13px]" style={{ color: '#6a7180' }}>
              Aucun document ne correspond à votre recherche.
            </p>
          )}

          {/* Sections par projet */}
          {shownSections.map((section) => (
            <section key={section.mid} className="space-y-3">
              <div className="flex items-center gap-2.5 border-b pb-2" style={{ borderColor: C.border }}>
                <span className="h-3 w-3 rounded-full" style={{ background: section.color }} />
                <h2 className="text-[15px]" style={{ fontFamily: SERIF, color: C.ink }}>{section.name}</h2>
                {roleByMonument[section.mid] && <RoleBadge role={roleByMonument[section.mid]!} />}
                <span className="text-[12px] tabular-nums" style={{ color: '#6a7180' }}>
                  {section.docs.length} document{section.docs.length > 1 ? 's' : ''}
                </span>
                <Link
                  to={ROUTES.PROJET_DETAIL(section.mid)}
                  className="ml-auto text-[12px] hover:underline"
                  style={{ color: C.blue }}
                  onClick={(e) => e.stopPropagation()}
                >
                  Voir le projet
                </Link>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {section.docs.map((doc) => (
                  <DocumentTile
                    key={`${section.mid}-${doc.id}`}
                    document={doc}
                    accentColor={section.color}
                    monumentNames={monumentNames}
                    dossiersById={dossiersById}
                    uploaderName={uploaderNames[doc.userId]}
                    myRole={roleByMonument[section.mid]}
                    sectionMonumentId={section.mid}
                    {...tileHandlers}
                  />
                ))}
              </div>
            </section>
          ))}

          {/* Sans projet */}
          {!activeProject && sansProjet.length > 0 && (
            <section className="space-y-3">
              <div className="flex items-center gap-2.5 border-b pb-2" style={{ borderColor: C.border }}>
                <span className="h-3 w-3 rounded-full" style={{ background: '#9aa1ad' }} />
                <h2 className="text-[15px]" style={{ fontFamily: SERIF, color: C.ink }}>Sans projet (personnels)</h2>
                <span className="text-[12px] tabular-nums" style={{ color: '#6a7180' }}>
                  {sansProjet.length} document{sansProjet.length > 1 ? 's' : ''}
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {sansProjet.map((doc) => (
                  <DocumentTile
                    key={`solo-${doc.id}`}
                    document={doc}
                    accentColor="#9aa1ad"
                    monumentNames={monumentNames}
                    dossiersById={dossiersById}
                    uploaderName={uploaderNames[doc.userId]}
                    myRole={null}
                    sectionMonumentId={null}
                    {...tileHandlers}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Autres documents partagés (projet non chargé / non membre) */}
          {!activeProject && orphanDocs.length > 0 && (
            <section className="space-y-3">
              <div className="flex items-center gap-2.5 border-b pb-2" style={{ borderColor: C.border }}>
                <span className="h-3 w-3 rounded-full" style={{ background: '#9aa1ad' }} />
                <h2 className="text-[15px]" style={{ fontFamily: SERIF, color: C.ink }}>Autres documents partagés</h2>
                <span className="text-[12px] tabular-nums" style={{ color: '#6a7180' }}>
                  {orphanDocs.length} document{orphanDocs.length > 1 ? 's' : ''}
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {orphanDocs.map((doc) => (
                  <DocumentTile
                    key={`orphan-${doc.id}`}
                    document={doc}
                    accentColor="#9aa1ad"
                    monumentNames={monumentNames}
                    dossiersById={dossiersById}
                    uploaderName={uploaderNames[doc.userId]}
                    myRole={null}
                    sectionMonumentId={null}
                    {...tileHandlers}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Corbeille */}
          {!activeProject && trashedDocuments.length > 0 && (
            <Collapsible open={trashOpen} onOpenChange={setTrashOpen}>
              <CollapsibleTrigger asChild>
                <button className="flex items-center gap-2 text-[13px] font-medium" style={{ color: '#6a7180' }}>
                  {trashOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                  <Trash2 className="h-3.5 w-3.5" />
                  Documents supprimés ({trashedDocuments.length})
                </button>
              </CollapsibleTrigger>
              <CollapsibleContent className="pt-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {trashedDocuments.map((doc) => (
                    <DocumentTile
                      key={`trash-${doc.id}`}
                      document={doc}
                      accentColor="#c0271d"
                      monumentNames={monumentNames}
                      dossiersById={dossiersById}
                      uploaderName={uploaderNames[doc.userId]}
                      myRole={null}
                      sectionMonumentId={null}
                      variant="trash"
                      {...tileHandlers}
                    />
                  ))}
                </div>
              </CollapsibleContent>
            </Collapsible>
          )}
        </div>
      )}

      {/* Dialogue de renommage */}
      <Dialog open={!!renameDoc} onOpenChange={(open) => { if (!open) setRenameDoc(null); }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader><DialogTitle>Renommer le document</DialogTitle></DialogHeader>
          <Input
            value={renameName}
            onChange={(e) => setRenameName(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleRenameSave(); }}
            autoFocus
            className="h-10 text-[14px]"
            style={{ background: C.card, borderColor: C.border }}
          />
          <DialogFooter>
            <button
              onClick={() => setRenameDoc(null)}
              disabled={renameLoading}
              className="px-4 py-2 text-[13px] font-medium border rounded-lg transition-colors"
              style={{ borderColor: C.border, color: '#5C6178' }}
            >
              Annuler
            </button>
            <button
              onClick={handleRenameSave}
              disabled={!renameName.trim() || renameLoading}
              className="px-4 py-2 text-[13px] font-semibold text-white rounded-lg disabled:opacity-50 hover:shadow-md transition-all"
              style={{ background: C.blue }}
            >
              {renameLoading ? 'Enregistrement…' : 'Enregistrer'}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <UploadDocumentDialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        onUploaded={(doc) => setAccessDoc(doc)}
      />
      {accessDoc && (
        <ManageDocumentAccessDialog
          document={accessDoc}
          myRole={roleByMonument[accessDoc.monumentIds[0]] ?? null}
          open={!!accessDoc}
          onOpenChange={(open) => { if (!open) setAccessDoc(null); }}
        />
      )}
      <DocumentPreviewDialog
        document={previewDoc}
        open={!!previewDoc}
        onOpenChange={(open) => { if (!open) setPreviewDoc(null); }}
        onAddToProject={(doc) => { setPreviewDoc(null); setAddToProjectDoc(doc); }}
      />
      <AddToProjectDialog
        document={addToProjectDoc}
        open={!!addToProjectDoc}
        onOpenChange={(open) => { if (!open) setAddToProjectDoc(null); }}
      />
    </div>
  );
}
