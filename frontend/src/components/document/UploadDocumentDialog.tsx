import { useRef, useState } from 'react';
import { Upload, File, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { formatFileSize } from '@/lib/format-utils';
import type { DocumentType } from '@/types';

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

interface UploadDocumentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function UploadDocumentDialog({ open, onOpenChange }: UploadDocumentDialogProps) {
  const user = useAuthStore((s) => s.user);
  const monuments = useMonumentStore((s) => s.monuments);
  const addDocument = useDocumentStore((s) => s.addDocument);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [nom, setNom] = useState('');
  const [type, setType] = useState<DocumentType | ''>('');
  const [monumentId, setMonumentId] = useState('');
  const [description, setDescription] = useState('');

  const userMonuments = user ? monuments.filter((m) => m.userId === user.id) : [];

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] ?? null;
    setFile(selected);
    if (selected && !nom) {
      // Pre-fill nom from filename (without extension)
      setNom(selected.name.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' '));
    }
  };

  const handleDropZoneClick = () => {
    fileInputRef.current?.click();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files[0];
    if (dropped) {
      setFile(dropped);
      if (!nom) {
        setNom(dropped.name.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' '));
      }
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !nom || !user) return;

    addDocument({
      nom,
      nomFichier: file.name,
      type: (type as DocumentType) || 'autre',
      tags: [],
      tailleFichier: file.size,
      mimeType: file.type,
      url: URL.createObjectURL(file),
      dossiersUtilises: [],
      ...(monumentId ? { monumentId } : {}),
      userId: user.id,
      description: description || undefined,
    });

    handleClose();
  };

  const handleClose = () => {
    setFile(null);
    setNom('');
    setType('');
    setMonumentId('');
    setDescription('');
    if (fileInputRef.current) fileInputRef.current.value = '';
    onOpenChange(false);
  };

  const isValid = !!file && !!nom.trim();

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Ajouter un document</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Drop zone */}
          <div
            onClick={handleDropZoneClick}
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            className="border-2 border-dashed border-muted-foreground/30 rounded-lg p-6 text-center cursor-pointer hover:border-primary/50 hover:bg-muted/30 transition-colors"
          >
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              onChange={handleFileChange}
            />
            {file ? (
              <div className="flex items-center justify-between gap-3 text-left">
                <div className="flex items-center gap-3 min-w-0">
                  <File className="h-8 w-8 text-primary shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{file.name}</p>
                    <p className="text-xs text-muted-foreground">{formatFileSize(file.size)}</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); setFile(null); }}
                  className="text-muted-foreground hover:text-foreground shrink-0"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                <Upload className="h-8 w-8 text-muted-foreground mx-auto" />
                <p className="text-sm text-muted-foreground">
                  Glissez un fichier ici ou <span className="text-primary font-medium">parcourez</span>
                </p>
              </div>
            )}
          </div>

          {/* Nom */}
          <div className="space-y-1.5">
            <Label htmlFor="doc-nom">Nom du document</Label>
            <Input
              id="doc-nom"
              placeholder="Ex : Devis restauration toiture"
              value={nom}
              onChange={(e) => setNom(e.target.value)}
            />
          </div>

          {/* Type + Monument */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Type</Label>
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
              <Label>Monument <span className="text-muted-foreground font-normal">(optionnel)</span></Label>
              <Select value={monumentId} onValueChange={setMonumentId}>
                <SelectTrigger>
                  <SelectValue placeholder="Aucun" />
                </SelectTrigger>
                <SelectContent>
                  {userMonuments.map((m) => (
                    <SelectItem key={m.id} value={m.id}>
                      {m.nom}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Description */}
          <div className="space-y-1.5">
            <Label htmlFor="doc-description">Description <span className="text-muted-foreground font-normal">(optionnel)</span></Label>
            <Textarea
              id="doc-description"
              placeholder="Courte description du document..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose}>
              Annuler
            </Button>
            <Button type="submit" disabled={!isValid}>
              <Upload className="h-4 w-4 mr-2" />
              Importer
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
