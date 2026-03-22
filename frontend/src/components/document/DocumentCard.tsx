import { useState } from 'react';
import { FileText, Image, FileSpreadsheet, File, FolderOpen, MoreVertical, Pencil, Trash2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { formatFileSize } from '@/lib/format-utils';
import { cn } from '@/lib/utils';
import type { Document } from '@/types';

interface DocumentCardProps {
  document: Document;
  dossierNames?: Record<string, string>;
  monumentNames?: Record<string, string>;
  onClick?: () => void;
  onRename?: (id: string, newName: string) => Promise<void>;
  onDelete?: (id: string) => Promise<void>;
}

const typeIcons: Record<string, typeof FileText> = {
  photo: Image,
  plan: FileSpreadsheet,
  devis: FileText,
  facture: FileText,
  attestation: FileText,
  extrait_cadastral: FileText,
  cerfa: FileText,
  arrete: FileText,
  diagnostic: FileText,
  rapport: FileText,
  correspondance: FileText,
  autre: File,
};

const typeLabels: Record<string, string> = {
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

const typeBg: Record<string, string> = {
  photo: 'bg-violet-50',
  plan: 'bg-blue-50',
  devis: 'bg-amber-50',
  facture: 'bg-orange-50',
  attestation: 'bg-green-50',
  extrait_cadastral: 'bg-teal-50',
  cerfa: 'bg-cyan-50',
  arrete: 'bg-red-50',
  diagnostic: 'bg-indigo-50',
  rapport: 'bg-slate-50',
  correspondance: 'bg-pink-50',
  autre: 'bg-gray-50',
};

const typeIconColor: Record<string, string> = {
  photo: 'text-violet-400',
  plan: 'text-blue-400',
  devis: 'text-amber-400',
  facture: 'text-orange-400',
  attestation: 'text-green-400',
  extrait_cadastral: 'text-teal-400',
  cerfa: 'text-cyan-400',
  arrete: 'text-red-400',
  diagnostic: 'text-indigo-400',
  rapport: 'text-slate-400',
  correspondance: 'text-pink-400',
  autre: 'text-gray-400',
};

export function DocumentCard({ document, dossierNames, monumentNames, onClick, onRename, onDelete }: DocumentCardProps) {
  const Icon = typeIcons[document.type] ?? File;
  const linkedMonuments = monumentNames
    ? document.monumentIds.map((id) => monumentNames[id]).filter(Boolean)
    : [];

  const linkedDossiers = dossierNames
    ? document.dossiersUtilises.map((id) => dossierNames[id]).filter(Boolean)
    : [];

  const [renameOpen, setRenameOpen] = useState(false);
  const [newName, setNewName] = useState(document.nom);
  const [loading, setLoading] = useState(false);

  const handleRename = async () => {
    if (!onRename || !newName.trim() || newName === document.nom) {
      setRenameOpen(false);
      return;
    }
    setLoading(true);
    try {
      await onRename(document.id, newName.trim());
      setRenameOpen(false);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!onDelete) return;
    if (!confirm(`Supprimer "${document.nom}" ? Le fichier sera supprimé définitivement.`)) return;
    await onDelete(document.id);
  };

  return (
    <>
    <Card className="hover:shadow-md transition-shadow overflow-hidden flex flex-col cursor-pointer relative" onClick={onClick}>
      <CardContent className="p-3 space-y-2 flex-1 flex flex-col">
        <div className="flex items-start gap-2.5">
          <div
            className={cn(
              'h-8 w-8 shrink-0 rounded flex items-center justify-center',
              typeBg[document.type] ?? 'bg-muted'
            )}
          >
            <Icon className={cn('h-4 w-4', typeIconColor[document.type] ?? 'text-muted-foreground')} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium leading-tight line-clamp-2">
              {document.nom}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5 truncate">
              {document.nomFichier}
            </p>
          </div>
          {(onRename || onDelete) && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                <button className="shrink-0 p-1 rounded hover:bg-muted transition-colors">
                  <MoreVertical className="h-4 w-4 text-muted-foreground" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
                {onRename && (
                  <DropdownMenuItem onClick={() => { setNewName(document.nom); setRenameOpen(true); }}>
                    <Pencil className="h-3.5 w-3.5 mr-2" />
                    Renommer
                  </DropdownMenuItem>
                )}
                {onDelete && (
                  <DropdownMenuItem className="text-destructive" onClick={handleDelete}>
                    <Trash2 className="h-3.5 w-3.5 mr-2" />
                    Supprimer
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="outline" className="text-xs">
            {typeLabels[document.type] ?? document.type}
          </Badge>
          <span className="text-xs text-muted-foreground">
            {formatFileSize(document.tailleFichier)}
          </span>
        </div>

        {linkedMonuments.length > 0 && (
          <p className="text-xs text-muted-foreground truncate">
            {linkedMonuments.join(', ')}
          </p>
        )}

        {document.description && (
          <p className="text-xs text-muted-foreground line-clamp-2">
            {document.description}
          </p>
        )}

        {/* Dossiers associés */}
        {linkedDossiers.length > 0 && (
          <div className="mt-auto pt-2 border-t space-y-1">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium flex items-center gap-1">
              <FolderOpen className="h-3 w-3" />
              Dossiers associés
            </p>
            {linkedDossiers.map((name) => (
              <p key={name} className="text-xs text-foreground truncate">
                {name}
              </p>
            ))}
          </div>
        )}

        {document.dossiersUtilises.length > 0 && linkedDossiers.length === 0 && (
          <p className="text-xs text-muted-foreground mt-auto pt-2 border-t">
            Utilisé dans {document.dossiersUtilises.length} dossier{document.dossiersUtilises.length > 1 ? 's' : ''}
          </p>
        )}
      </CardContent>
    </Card>

    <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
      <DialogContent className="sm:max-w-sm" onClick={(e) => e.stopPropagation()}>
        <DialogHeader>
          <DialogTitle>Renommer le document</DialogTitle>
        </DialogHeader>
        <Input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleRename(); }}
          autoFocus
        />
        <DialogFooter>
          <Button variant="outline" onClick={() => setRenameOpen(false)} disabled={loading}>
            Annuler
          </Button>
          <Button onClick={handleRename} disabled={!newName.trim() || loading}>
            {loading ? 'Enregistrement...' : 'Enregistrer'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    </>
  );
}
