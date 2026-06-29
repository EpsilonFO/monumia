import { useState } from 'react';
import { Receipt, Image, FileSpreadsheet, FileArchive, FolderOpen, FolderPlus, MoreVertical, Pencil, Trash2, ScrollText, Scale, FileSearch, PenTool, FileText, Stamp, FileBadge, ClipboardList, Lock, ShieldCheck } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { formatFileSize } from '@/lib/format-utils';
import { canDeleteDocument } from '@/lib/project-permissions';
import { canEditVisibility } from '@/lib/document-visibility';
import { ManageDocumentAccessDialog } from './ManageDocumentAccessDialog';
import { useAuthStore } from '@/stores/useAuthStore';
import type { Document, ProjectRole } from '@/types';

interface DocumentCardProps {
  document: Document;
  dossierNames?: Record<string, string>;
  monumentNames?: Record<string, string>;
  onClick?: () => void;
  onRename?: (id: string, newName: string) => Promise<void>;
  onDelete?: (id: string) => Promise<void>;
  onAddToProject?: (document: Document) => void;
  myRole?: ProjectRole | null;
  uploaderName?: string;
  /** Appelé après un changement d'accès, pour rafraîchir la liste du parent. */
  onDocumentUpdated?: () => void;
}

const typeIcons: Record<string, typeof FileText> = {
  photo: Image, plan: FileSpreadsheet, devis: ClipboardList, facture: Receipt,
  attestation: FileBadge, extrait_cadastral: FileSpreadsheet, cerfa: Stamp,
  arrete: Scale, diagnostic: FileSearch, rapport: ScrollText, correspondance: PenTool, autre: FileArchive,
};

const typeLabels: Record<string, string> = {
  photo: 'Photo', plan: 'Plan', devis: 'Devis', facture: 'Facture',
  attestation: 'Attestation', extrait_cadastral: 'Extrait cadastral', cerfa: 'CERFA',
  arrete: 'Arrêté', diagnostic: 'Diagnostic', rapport: 'Rapport', correspondance: 'Correspondance', autre: 'Autre',
};

const typeAccent: Record<string, { bg: string; text: string }> = {
  photo:             { bg: 'var(--cat-violet-soft)',    text: 'var(--cat-violet)' },
  plan:              { bg: 'var(--secondary)',          text: 'var(--primary)' },
  devis:             { bg: 'var(--warning-muted)',      text: 'var(--warning)' },
  facture:           { bg: 'var(--destructive-muted)',  text: 'var(--destructive)' },
  attestation:       { bg: 'var(--success-muted)',      text: 'var(--success)' },
  extrait_cadastral: { bg: 'var(--cat-teal-soft)',      text: 'var(--cat-teal)' },
  cerfa:             { bg: 'var(--info-muted)',         text: 'var(--info)' },
  arrete:            { bg: 'var(--destructive-muted)',  text: 'var(--destructive)' },
  diagnostic:        { bg: 'var(--secondary)',          text: 'var(--primary)' },
  rapport:           { bg: 'var(--muted)',              text: 'var(--muted-foreground)' },
  correspondance:    { bg: 'var(--cat-burgundy-soft)',   text: 'var(--cat-burgundy)' },
  autre:             { bg: 'var(--muted)',              text: 'var(--muted-foreground)' },
};

export function DocumentCard({ document, dossierNames, monumentNames, onClick, onRename, onDelete, onAddToProject, myRole, uploaderName, onDocumentUpdated }: DocumentCardProps) {
  const currentUserId = useAuthStore((s) => s.user?.id);
  const isUploader = document.userId === currentUserId;
  // Suppression / renommage : l'auteur, ou un owner/co_owner du projet (tous les
  // droits sur les docs). Un membre ne peut agir que sur les siens. Consultation
  // ouverte à tous.
  const canModify = canDeleteDocument(isUploader, myRole);
  const canManageAccess = canEditVisibility(isUploader, myRole);
  const isRestricted = document.visibility !== 'team';
  const [accessOpen, setAccessOpen] = useState(false);

  const Icon = typeIcons[document.type] ?? FileText;
  const accent = typeAccent[document.type] ?? typeAccent.autre;
  const linkedMonuments = monumentNames ? document.monumentIds.map((id) => monumentNames[id]).filter(Boolean) : [];
  const linkedDossiers = dossierNames ? document.dossiersUtilises.map((id) => dossierNames[id]).filter(Boolean) : [];

  const [renameOpen, setRenameOpen] = useState(false);
  const [newName, setNewName] = useState(document.nom);
  const [loading, setLoading] = useState(false);

  const handleRename = async () => {
    if (!onRename || !newName.trim() || newName === document.nom) { setRenameOpen(false); return; }
    setLoading(true);
    try { await onRename(document.id, newName.trim()); setRenameOpen(false); }
    finally { setLoading(false); }
  };

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!onDelete) return;
    if (!confirm(`Supprimer "${document.nom}" ?`)) return;
    await onDelete(document.id);
  };

  return (
    <>
      <div
        onClick={onClick}
        className="group relative bg-card rounded-xl border border-border/80 overflow-hidden cursor-pointer transition-all duration-200 hover:shadow-md hover:shadow-black/[0.03] hover:border-border"
      >
        {/* Top accent strip */}
        <div className="h-1" style={{ background: accent.text }} />

        <div className="p-4 space-y-2.5">
          {/* Header row */}
          <div className="flex items-start gap-2.5">
            <div
              className="h-8 w-8 shrink-0 rounded-lg flex items-center justify-center"
              style={{ background: accent.bg }}
            >
              <Icon className="h-4 w-4" style={{ color: accent.text }} strokeWidth={1.8} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-semibold text-foreground leading-tight line-clamp-1">{document.nom}</p>
              <p className="text-[11px] text-muted-foreground mt-0.5 truncate">{document.nomFichier}</p>
              {uploaderName && (
                <p className="text-[11px] text-muted-foreground">Ajouté par {uploaderName}</p>
              )}
            </div>
            {((onRename && canModify) || (onDelete && canModify) || onAddToProject || canManageAccess) && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                  <button className="shrink-0 p-1 rounded-md hover:bg-muted transition-colors opacity-0 group-hover:opacity-100">
                    <MoreVertical className="h-3.5 w-3.5 text-muted-foreground" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
                  {onAddToProject && (
                    <DropdownMenuItem onClick={() => onAddToProject(document)}>
                      <FolderPlus className="h-3.5 w-3.5 mr-2" />Ajouter à un projet
                    </DropdownMenuItem>
                  )}
                  {canManageAccess && (
                    <DropdownMenuItem onClick={() => setAccessOpen(true)}>
                      <ShieldCheck className="h-3.5 w-3.5 mr-2" />Gérer l'accès
                    </DropdownMenuItem>
                  )}
                  {onRename && canModify && (
                    <DropdownMenuItem onClick={() => { setNewName(document.nom); setRenameOpen(true); }}>
                      <Pencil className="h-3.5 w-3.5 mr-2" />Renommer
                    </DropdownMenuItem>
                  )}
                  {onDelete && canModify && (
                    <DropdownMenuItem className="text-destructive" onClick={handleDelete}>
                      <Trash2 className="h-3.5 w-3.5 mr-2" />Supprimer
                    </DropdownMenuItem>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>

          {/* Meta row */}
          <div className="flex items-center gap-2">
            <Badge
              className="text-[10px] font-semibold border-0 px-1.5 py-0.5"
              style={{ background: accent.bg, color: accent.text }}
            >
              {typeLabels[document.type] ?? document.type}
            </Badge>
            <span className="text-[11px] text-muted-foreground">{formatFileSize(document.tailleFichier)}</span>
            {isRestricted && (
              <span
                className="inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-semibold bg-destructive-muted text-destructive"
                title="Visible uniquement par certaines personnes"
              >
                <Lock className="h-2.5 w-2.5" />
                Accès restreint
              </span>
            )}
          </div>

          {/* Monument link */}
          {linkedMonuments.length > 0 && (
            <p className="text-[11px] text-muted-foreground truncate">{linkedMonuments.join(', ')}</p>
          )}

          {/* Dossiers */}
          {linkedDossiers.length > 0 && (
            <div className="pt-2 border-t border-border/60">
              <p className="text-[10px] uppercase tracking-[0.08em] font-semibold text-muted-foreground flex items-center gap-1 mb-1">
                <FolderOpen className="h-3 w-3" strokeWidth={1.8} />Dossiers
              </p>
              {linkedDossiers.map((name) => (
                <p key={name} className="text-[11px] text-foreground truncate">{name}</p>
              ))}
            </div>
          )}

          {document.dossiersUtilises.length > 0 && linkedDossiers.length === 0 && (
            <p className="text-[11px] text-muted-foreground pt-2 border-t border-border/60">
              Utilisé dans {document.dossiersUtilises.length} dossier{document.dossiersUtilises.length > 1 ? 's' : ''}
            </p>
          )}
        </div>
      </div>

      <ManageDocumentAccessDialog
        document={document}
        myRole={myRole ?? null}
        open={accessOpen}
        onOpenChange={setAccessOpen}
        onSaved={onDocumentUpdated}
      />

      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent className="sm:max-w-sm" onClick={(e) => e.stopPropagation()}>
          <DialogHeader><DialogTitle>Renommer le document</DialogTitle></DialogHeader>
          <Input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleRename(); }}
            autoFocus
            className="h-10 text-[14px] bg-card border-border focus:border-primary focus:ring-primary/10"
          />
          <DialogFooter>
            <button onClick={() => setRenameOpen(false)} disabled={loading} className="px-4 py-2 text-[13px] font-medium border border-border rounded-lg text-muted-foreground hover:bg-muted transition-colors">
              Annuler
            </button>
            <button onClick={handleRename} disabled={!newName.trim() || loading} className="px-4 py-2 text-[13px] font-semibold text-primary-foreground bg-primary rounded-lg disabled:opacity-50 hover:shadow-md transition-all">
              {loading ? 'Enregistrement...' : 'Enregistrer'}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
