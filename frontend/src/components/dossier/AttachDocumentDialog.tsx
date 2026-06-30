import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, Loader2, X } from 'lucide-react';
import { IconDocument, IconRecherche, IconDepot } from '@/components/icons';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { formatFileSize } from '@/lib/format-utils';
import { useAuthStore } from '@/stores/useAuthStore';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { ACCEPT_ATTR, MAX_FILE_SIZE_MB, validateFile } from '@/constants/file-types';
import { toast } from 'sonner';
import type { Document, DocumentType } from '@/types';

const TYPE_LABELS: Record<DocumentType, string> = {
  photo: 'Photo',
  plan: 'Plan',
  devis: 'Devis',
  facture: 'Facture',
  attestation: 'Attestation',
  extrait_cadastral: 'Extrait cadastral',
  cerfa: 'CERFA',
  arrete: 'Arrêté',
  diagnostic: 'Diagnostic',
  rapport: 'Rapport',
  correspondance: 'Correspondance',
  autre: 'Autre',
};

interface AttachDocumentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Optional monument to pre-filter the "my documents" list and tag uploads. */
  monumentId?: string;
  /** Default name suggested when uploading (the checklist item label). */
  defaultName?: string;
  /** Called with the chosen document (either existing or freshly uploaded). */
  onAttach: (document: Document) => Promise<void> | void;
  /** Called only after a FRESH upload (pas la sélection d'un doc existant) —
   *  pour ouvrir le popup « Gérer l'accès » sur la pièce déposée. */
  onUploaded?: (document: Document) => void;
}

export function AttachDocumentDialog({
  open,
  onOpenChange,
  monumentId,
  defaultName,
  onAttach,
  onUploaded,
}: AttachDocumentDialogProps) {
  const user = useAuthStore((s) => s.user);
  const { documents, loading, fetchDocuments, uploadDocument } = useDocumentStore();

  const [search, setSearch] = useState('');
  // Par défaut on montre TOUS les documents de l'utilisateur (pas seulement ceux
  // déjà dans ce projet) : on peut ainsi rattacher un doc de « Mes documents ».
  const [scope, setScope] = useState<'monument' | 'all'>('all');
  const [attachingId, setAttachingId] = useState<string | null>(null);

  // Upload form state
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [nom, setNom] = useState('');
  const [type, setType] = useState<DocumentType | ''>('');
  const [description, setDescription] = useState('');
  const [uploading, setUploading] = useState(false);

  // Reset on open
  useEffect(() => {
    if (open) {
      fetchDocuments();
      setSearch('');
      setScope('all');
      setFile(null);
      setNom(defaultName ?? '');
      setType('');
      setDescription('');
    }
  }, [open, monumentId, defaultName, fetchDocuments]);

  const filtered = useMemo(() => {
    let docs = documents;
    if (scope === 'monument' && monumentId) {
      docs = docs.filter((d) => d.monumentIds.includes(monumentId));
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      docs = docs.filter(
        (d) =>
          d.nom.toLowerCase().includes(q) ||
          d.nomFichier.toLowerCase().includes(q) ||
          d.tags.some((t) => t.toLowerCase().includes(q)),
      );
    }
    return docs;
  }, [documents, scope, monumentId, search]);

  const handleSelectExisting = async (doc: Document) => {
    setAttachingId(doc.id);
    try {
      await onAttach(doc);
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors de la sélection');
    } finally {
      setAttachingId(null);
    }
  };

  const acceptFile = (candidate: File) => {
    const err = validateFile(candidate);
    if (err) {
      toast.error(err);
      return;
    }
    setFile(candidate);
    if (!nom) {
      setNom(candidate.name.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' '));
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) acceptFile(selected);
    e.target.value = '';
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files[0];
    if (dropped) acceptFile(dropped);
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !nom.trim() || !type || !user) return;

    setUploading(true);
    try {
      const doc = await uploadDocument(
        {
          file,
          nom: nom.trim(),
          type: type as DocumentType,
          monumentIds: monumentId ? [monumentId] : undefined,
          description: description.trim() || undefined,
          tags: [],
        },
        user.id,
      );
      await onAttach(doc);
      onUploaded?.(doc);
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur lors de l'import");
    } finally {
      setUploading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Ajouter un document</DialogTitle>
        </DialogHeader>

        <div className="flex-1 min-h-0 overflow-y-auto space-y-5 pr-1">
          {/* 1 — Téléverser un nouveau document */}
          <section className="space-y-3">
            <h3 className="text-[13px] font-semibold text-foreground">Téléverser un nouveau document</h3>
            <form onSubmit={handleUpload} className="space-y-3">
              <div
                onClick={() => fileInputRef.current?.click()}
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
                className="border-2 border-dashed border-muted-foreground/30 rounded-lg p-6 text-center cursor-pointer hover:border-primary/50 hover:bg-muted/30 transition-colors"
              >
                <input ref={fileInputRef} type="file" accept={ACCEPT_ATTR} className="hidden" onChange={handleFileChange} />
                {file ? (
                  <div className="flex items-center justify-between gap-3 text-left">
                    <div className="flex items-center gap-3 min-w-0">
                      <IconDocument className="h-8 w-8 text-primary shrink-0" />
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate">{file.name}</p>
                        <p className="text-xs text-muted-foreground">{formatFileSize(file.size)}</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setFile(null);
                      }}
                      className="text-muted-foreground hover:text-foreground shrink-0"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <IconDepot className="h-8 w-8 text-muted-foreground mx-auto" />
                    <p className="text-sm text-muted-foreground">
                      Glissez un fichier ici ou <span className="text-primary font-medium">parcourez</span>
                    </p>
                    <p className="text-[11px] text-muted-foreground/70">
                      PDF, images, Word, Excel, CSV · max {MAX_FILE_SIZE_MB} Mo
                    </p>
                  </div>
                )}
              </div>

              {/* Détails + bouton d'import : seulement une fois un fichier choisi. */}
              {file && (
                <div className="space-y-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="attach-nom">Nom du document *</Label>
                    <Input
                      id="attach-nom"
                      placeholder="Ex : Devis restauration toiture"
                      value={nom}
                      onChange={(e) => setNom(e.target.value)}
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label>Type *</Label>
                    <Select value={type} onValueChange={(v) => setType(v as DocumentType)}>
                      <SelectTrigger>
                        <SelectValue placeholder="Choisir..." />
                      </SelectTrigger>
                      <SelectContent>
                        {(Object.entries(TYPE_LABELS) as [DocumentType, string][]).map(([value, label]) => (
                          <SelectItem key={value} value={value}>
                            {label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="attach-description">
                      Description <span className="text-muted-foreground font-normal">(optionnel)</span>
                    </Label>
                    <Textarea
                      id="attach-description"
                      placeholder="Courte description…"
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      rows={2}
                    />
                  </div>

                  <div className="flex justify-end">
                    <Button type="submit" disabled={!file || !nom.trim() || !type || uploading}>
                      {uploading ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Import en cours…
                        </>
                      ) : (
                        <>
                          <IconDepot className="h-4 w-4 mr-2" />
                          Importer et rattacher
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              )}
            </form>
          </section>

          {/* Séparation claire entre « téléverser » et « choisir un existant ». */}
          <div className="flex items-center gap-3">
            <span className="h-px flex-1 bg-border" />
            <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
              ou choisir parmi mes documents
            </span>
            <span className="h-px flex-1 bg-border" />
          </div>

          {/* 2 — Choisir un document existant (« Mes documents ») */}
          <section className="space-y-3">
            <div className="flex gap-2">
              <div className="relative flex-1">
                <IconRecherche className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  className="pl-9"
                  placeholder="Rechercher dans mes documents..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              {monumentId && (
                <Select value={scope} onValueChange={(v) => setScope(v as 'monument' | 'all')}>
                  <SelectTrigger className="w-48">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Tous mes documents</SelectItem>
                    <SelectItem value="monument">Ce projet uniquement</SelectItem>
                  </SelectContent>
                </Select>
              )}
            </div>

            <div className="max-h-64 overflow-y-auto border rounded-lg">
              {loading ? (
                <div className="flex items-center justify-center py-10">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              ) : filtered.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-10 gap-2 text-muted-foreground">
                  <IconDocument className="h-8 w-8 opacity-50" />
                  <p className="text-sm text-center px-4">
                    Aucun document existant — utilisez la zone de téléversement ci-dessus.
                  </p>
                </div>
              ) : (
                <ul className="divide-y">
                  {filtered.map((doc) => {
                    const busy = attachingId === doc.id;
                    return (
                      <li key={doc.id}>
                        <button
                          type="button"
                          disabled={!!attachingId}
                          onClick={() => handleSelectExisting(doc)}
                          className={cn(
                            'w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-muted/50 transition-colors',
                            attachingId && !busy && 'opacity-50 cursor-not-allowed',
                          )}
                        >
                          <IconDocument className="h-5 w-5 text-muted-foreground shrink-0" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium truncate">{doc.nom}</span>
                              <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4 shrink-0">
                                {TYPE_LABELS[doc.type] ?? doc.type}
                              </Badge>
                            </div>
                            <p className="text-xs text-muted-foreground truncate">
                              {doc.nomFichier} · {formatFileSize(doc.tailleFichier)}
                            </p>
                          </div>
                          {busy ? (
                            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground shrink-0" />
                          ) : (
                            <Check className="h-4 w-4 text-muted-foreground/40 shrink-0" />
                          )}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </section>
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={uploading || !!attachingId}
          >
            Fermer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
