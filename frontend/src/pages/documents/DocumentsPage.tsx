import { useEffect, useMemo, useState } from 'react';
import { Upload, Search, FolderOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { DocumentCard } from '@/components/document/DocumentCard';
import { UploadDocumentDialog } from '@/components/document/UploadDocumentDialog';
import { useAuthStore } from '@/stores/useAuthStore';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';

export function DocumentsPage() {
  const user = useAuthStore((s) => s.user);
  const { documents, loading, fetchDocuments } = useDocumentStore();
  const monuments = useMonumentStore((s) => s.monuments);
  const dossiers = useDossierStore((s) => s.dossiers);

  const [search, setSearch] = useState('');
  const [filterMonument, setFilterMonument] = useState('all');
  const [filterType, setFilterType] = useState('all');
  const [uploadOpen, setUploadOpen] = useState(false);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const dossierNames = useMemo(() => {
    const map: Record<string, string> = {};
    dossiers.forEach((d) => { map[d.id] = d.titre; });
    return map;
  }, [dossiers]);

  const filteredDocuments = useMemo(() => {
    let docs = documents;

    if (filterMonument !== 'all') {
      docs = docs.filter((d) => d.monumentId === filterMonument);
    }
    if (filterType !== 'all') {
      docs = docs.filter((d) => d.type === filterType);
    }
    if (search) {
      const q = search.toLowerCase();
      docs = docs.filter(
        (d) =>
          d.nom.toLowerCase().includes(q) ||
          d.nomFichier.toLowerCase().includes(q) ||
          d.tags.some((t) => t.toLowerCase().includes(q))
      );
    }

    return docs;
  }, [documents, search, filterMonument, filterType]);

  const userMonuments = useMemo(
    () => (user ? monuments.filter((m) => m.userId === user.id) : []),
    [monuments, user]
  );

  const docTypes = useMemo(() => {
    const types = new Set(documents.map((d) => d.type));
    return Array.from(types).sort();
  }, [documents]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mes documents"
        description="Bibliothèque documentaire de vos monuments"
        action={
          <Button onClick={() => setUploadOpen(true)}>
            <Upload className="h-4 w-4 mr-2" />
            Ajouter un document
          </Button>
        }
      />

      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Rechercher un document..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select value={filterMonument} onValueChange={setFilterMonument}>
          <SelectTrigger className="w-full sm:w-48">
            <SelectValue placeholder="Monument" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous les monuments</SelectItem>
            {userMonuments.map((m) => (
              <SelectItem key={m.id} value={m.id}>
                {m.nom}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={filterType} onValueChange={setFilterType}>
          <SelectTrigger className="w-full sm:w-40">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous les types</SelectItem>
            {docTypes.map((t) => (
              <SelectItem key={t} value={t}>
                {t}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-48 rounded-lg bg-muted animate-pulse" />
          ))}
        </div>
      ) : filteredDocuments.length === 0 ? (
        <EmptyState
          icon={FolderOpen}
          title="Aucun document"
          description={
            search
              ? 'Aucun document ne correspond à votre recherche.'
              : 'Ajoutez vos premiers documents pour les utiliser dans vos dossiers.'
          }
          action={
            !search ? (
              <Button onClick={() => setUploadOpen(true)}>
                <Upload className="h-4 w-4 mr-2" />
                Ajouter un document
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredDocuments.map((doc) => (
            <DocumentCard key={doc.id} document={doc} dossierNames={dossierNames} />
          ))}
        </div>
      )}

      <UploadDocumentDialog open={uploadOpen} onOpenChange={setUploadOpen} />
    </div>
  );
}
