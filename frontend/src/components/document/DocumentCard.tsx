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
  photo: { bg: '#F3E8FF', text: '#7C3AED' },
  plan: { bg: '#E8EAF6', text: '#1A237E' },
  devis: { bg: '#FEF3C7', text: '#92400E' },
  facture: { bg: '#FBF0EC', text: '#C75B3A' },
  attestation: { bg: '#ECFDF5', text: '#065F46' },
  extrait_cadastral: { bg: '#E0F2F1', text: '#00695C' },
  cerfa: { bg: '#E0F7FA', text: '#006064' },
  arrete: { bg: '#FFEBEE', text: '#B71C1C' },
  diagnostic: { bg: '#E8EAF6', text: '#283593' },
  rapport: { bg: '#F1F5F9', text: '#334155' },
  correspondance: { bg: '#FCE4EC', text: '#880E4F' },
  autre: { bg: '#F3F4F6', text: '#374151' },
};

export function DocumentCard({ document, dossierNames, monumentNames, onClick, onRename, onDelete, onAddToProject, myRole, uploaderName }: DocumentCardProps) {
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
        className="group relative bg-white rounded-xl border border-[#E4E2DC]/80 overflow-hidden cursor-pointer transition-all duration-200 hover:shadow-md hover:shadow-black/[0.03] hover:border-[#E4E2DC]"
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
              <p className="text-[13px] font-semibold text-[#1B1E2E] leading-tight line-clamp-1">{document.nom}</p>
              <p className="text-[11px] text-[#8E92A4] mt-0.5 truncate">{document.nomFichier}</p>
              {uploaderName && (
                <p className="text-[11px] text-[#8E92A4]">Ajouté par {uploaderName}</p>
              )}
            </div>
            {((onRename && canModify) || (onDelete && canModify) || onAddToProject || canManageAccess) && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                  <button className="shrink-0 p-1 rounded-md hover:bg-[#F8F7F4] transition-colors opacity-0 group-hover:opacity-100">
                    <MoreVertical className="h-3.5 w-3.5 text-[#8E92A4]" />
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
            <span className="text-[11px] text-[#8E92A4]">{formatFileSize(document.tailleFichier)}</span>
            {isRestricted && (
              <span
                className="inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
                style={{ background: '#FBEAE8', color: '#C0271D' }}
                title="Visible uniquement par certaines personnes"
              >
                <Lock className="h-2.5 w-2.5" />
                Accès restreint
              </span>
            )}
          </div>

          {/* Monument link */}
          {linkedMonuments.length > 0 && (
            <p className="text-[11px] text-[#8E92A4] truncate">{linkedMonuments.join(', ')}</p>
          )}

          {/* Dossiers */}
          {linkedDossiers.length > 0 && (
            <div className="pt-2 border-t border-[#E4E2DC]/60">
              <p className="text-[10px] uppercase tracking-[0.08em] font-semibold text-[#8E92A4] flex items-center gap-1 mb-1">
                <FolderOpen className="h-3 w-3" strokeWidth={1.8} />Dossiers
              </p>
              {linkedDossiers.map((name) => (
                <p key={name} className="text-[11px] text-[#1B1E2E] truncate">{name}</p>
              ))}
            </div>
          )}

          {document.dossiersUtilises.length > 0 && linkedDossiers.length === 0 && (
            <p className="text-[11px] text-[#8E92A4] pt-2 border-t border-[#E4E2DC]/60">
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
      />

      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent className="sm:max-w-sm" onClick={(e) => e.stopPropagation()}>
          <DialogHeader><DialogTitle>Renommer le document</DialogTitle></DialogHeader>
          <Input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleRename(); }}
            autoFocus
            className="h-10 text-[14px] bg-white border-[#E4E2DC] focus:border-[#1A237E] focus:ring-[#1A237E]/10"
          />
          <DialogFooter>
            <button onClick={() => setRenameOpen(false)} disabled={loading} className="px-4 py-2 text-[13px] font-medium border border-[#E4E2DC] rounded-lg text-[#5C6178] hover:bg-[#F8F7F4] transition-colors">
              Annuler
            </button>
            <button onClick={handleRename} disabled={!newName.trim() || loading} className="px-4 py-2 text-[13px] font-semibold text-white rounded-lg disabled:opacity-50 hover:shadow-md transition-all" style={{ background: '#1A237E' }}>
              {loading ? 'Enregistrement...' : 'Enregistrer'}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
