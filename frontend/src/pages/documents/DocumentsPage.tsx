import { useEffect, useMemo, useState } from 'react';
import { Upload, Search, FolderOpen } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { DocumentCard } from '@/components/document/DocumentCard';
import { DocumentPreviewDialog } from '@/components/document/DocumentPreviewDialog';
import { UploadDocumentDialog } from '@/components/document/UploadDocumentDialog';
import { AddToProjectDialog } from '@/components/document/AddToProjectDialog';
import { useAuthStore } from '@/stores/useAuthStore';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { toast } from 'sonner';

export function DocumentsPage() {
  const user = useAuthStore((s) => s.user);
  const { documents, loading, fetchDocuments, updateDocument, deleteDocument } = useDocumentStore();
  const monuments = useMonumentStore((s) => s.monuments);
  const dossiers = useDossierStore((s) => s.dossiers);

  const [search, setSearch] = useState('');
  const [filterMonument, setFilterMonument] = useState('all');
  const [filterType, setFilterType] = useState('all');
  const [uploadOpen, setUploadOpen] = useState(false);
  const [previewDoc, setPreviewDoc] = useState<typeof documents[number] | null>(null);
  const [addToProjectDoc, setAddToProjectDoc] = useState<typeof documents[number] | null>(null);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const dossierNames = useMemo(() => {
    const map: Record<string, string> = {};
    dossiers.forEach((d) => { map[d.id] = d.titre; });
    return map;
  }, [dossiers]);

  const monumentNames = useMemo(() => {
    const map: Record<string, string> = {};
    monuments.forEach((m) => { map[m.id] = m.nom; });
    return map;
  }, [monuments]);

  const filteredDocuments = useMemo(() => {
    let docs = documents;
    if (filterMonument !== 'all') docs = docs.filter((d) => d.monumentIds.includes(filterMonument));
    if (filterType !== 'all') docs = docs.filter((d) => d.type === filterType);
    if (search) {
      const q = search.toLowerCase();
      docs = docs.filter((d) => d.nom.toLowerCase().includes(q) || d.nomFichier.toLowerCase().includes(q) || d.tags.some((t) => t.toLowerCase().includes(q)));
    }
    return docs;
  }, [documents, search, filterMonument, filterType]);

  const userMonuments = useMemo(() => (user ? monuments.filter((m) => m.userId === user.id) : []), [monuments, user]);
  const docTypes = useMemo(() => Array.from(new Set(documents.map((d) => d.type))).sort(), [documents]);

  const handleRename = async (id: string, newName: string) => {
    try { await updateDocument(id, { nom: newName }); toast.success('Document renommé'); }
    catch (err) { toast.error(err instanceof Error ? err.message : 'Erreur lors du renommage'); }
  };

  const handleDelete = async (id: string) => {
    try { await deleteDocument(id); toast.success('Document supprimé'); }
    catch (err) { toast.error(err instanceof Error ? err.message : 'Erreur lors de la suppression'); }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mes documents"
        description="Bibliothèque documentaire de vos monuments"
        action={
          <button
            onClick={() => setUploadOpen(true)}
            className="inline-flex items-center gap-2 px-5 py-2.5 text-[13px] font-semibold text-white rounded-lg transition-all duration-300 hover:shadow-md"
            style={{ background: '#1A237E' }}
          >
            <Upload className="h-3.5 w-3.5" strokeWidth={1.8} />
            Ajouter un document
          </button>
        }
      />

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#8E92A4]" />
          <Input
            className="pl-9 h-10 text-[14px] bg-white border-[#E4E2DC] focus:border-[#1A237E] focus:ring-[#1A237E]/10"
            placeholder="Rechercher un document..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select value={filterMonument} onValueChange={setFilterMonument}>
          <SelectTrigger className="w-full sm:w-48 h-10 text-[14px] bg-white border-[#E4E2DC]">
            <SelectValue placeholder="Monument" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous les monuments</SelectItem>
            {userMonuments.map((m) => (<SelectItem key={m.id} value={m.id}>{m.nom}</SelectItem>))}
          </SelectContent>
        </Select>
        <Select value={filterType} onValueChange={setFilterType}>
          <SelectTrigger className="w-full sm:w-40 h-10 text-[14px] bg-white border-[#E4E2DC]">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous les types</SelectItem>
            {docTypes.map((t) => (<SelectItem key={t} value={t}>{t}</SelectItem>))}
          </SelectContent>
        </Select>
      </div>

      {/* Content */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-48 rounded-xl bg-[#E4E2DC]/30 animate-pulse" />
          ))}
        </div>
      ) : filteredDocuments.length === 0 ? (
        <EmptyState
          icon={FolderOpen}
          title="Aucun document"
          description={search ? 'Aucun document ne correspond à votre recherche.' : 'Ajoutez vos premiers documents pour les utiliser dans vos dossiers.'}
          action={!search ? (
            <button
              onClick={() => setUploadOpen(true)}
              className="inline-flex items-center gap-2 px-5 py-2.5 text-[13px] font-semibold text-white rounded-lg transition-all duration-300 hover:shadow-md"
              style={{ background: '#1A237E' }}
            >
              <Upload className="h-3.5 w-3.5" strokeWidth={1.8} />
              Ajouter un document
            </button>
          ) : undefined}
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredDocuments.map((doc) => (
            <DocumentCard key={doc.id} document={doc} dossierNames={dossierNames} monumentNames={monumentNames} onClick={() => setPreviewDoc(doc)} onRename={handleRename} onDelete={handleDelete} onAddToProject={(doc) => { setPreviewDoc(null); setAddToProjectDoc(doc); }} />
          ))}
        </div>
      )}

      <UploadDocumentDialog open={uploadOpen} onOpenChange={setUploadOpen} />
      <DocumentPreviewDialog document={previewDoc} open={!!previewDoc} onOpenChange={(open) => { if (!open) setPreviewDoc(null); }} onAddToProject={(doc) => { setPreviewDoc(null); setAddToProjectDoc(doc); }} />
      <AddToProjectDialog
        document={addToProjectDoc}
        open={!!addToProjectDoc}
        onOpenChange={(open) => { if (!open) setAddToProjectDoc(null); }}
      />
    </div>
  );
}
