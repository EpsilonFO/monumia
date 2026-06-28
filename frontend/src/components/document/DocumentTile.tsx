import { FolderPlus, MoreVertical, Trash2, Lock, RotateCcw, Eye, FolderMinus, Pencil } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { C } from '@/lib/brand';
import { formatFileSize } from '@/lib/format-utils';
import { canDeleteDocument } from '@/lib/project-permissions';
import { VISIBILITY_META } from '@/lib/document-visibility';
import { typeIcon, typeLabel, typeAccent } from '@/lib/document-type-meta';
import { DocumentLocationsPopover } from '@/components/document/DocumentLocationsPopover';
import { useAuthStore } from '@/stores/useAuthStore';
import type { Document, ProjectRole } from '@/types';

interface DocumentTileProps {
  document: Document;
  accentColor: string;
  monumentNames: Record<string, string>;
  dossiersById: Record<string, { titre: string; monumentId: string }>;
  uploaderName?: string;
  myRole?: ProjectRole | null;
  sectionMonumentId: string | null;
  variant?: 'normal' | 'trash';
  onPreview: (d: Document) => void;
  onAddToProject: (d: Document) => void;
  onRename?: (d: Document) => void;
  onTrash: (d: Document) => void;
  onRemoveFromProject: (d: Document, monumentId: string) => void;
  onRestore: (d: Document) => void;
  onDeletePermanent: (d: Document) => void;
}

export function DocumentTile({
  document, accentColor, monumentNames, dossiersById, uploaderName, myRole,
  sectionMonumentId, variant = 'normal',
  onPreview, onAddToProject, onRename, onTrash, onRemoveFromProject, onRestore, onDeletePermanent,
}: DocumentTileProps) {
  const currentUserId = useAuthStore((s) => s.user?.id);
  const isUploader = document.userId === currentUserId;
  const canModify = canDeleteDocument(isUploader, myRole);
  const Icon = typeIcon(document.type);
  const accent = typeAccent(document.type);
  const restricted = document.visibility !== 'team';
  const multiProject = document.monumentIds.length > 1;

  const stop = (e: React.MouseEvent) => e.stopPropagation();

  return (
    <div
      onClick={() => onPreview(document)}
      className="group relative flex flex-col overflow-hidden rounded-xl border cursor-pointer transition-all duration-200 hover:shadow-md"
      style={{ background: C.card, borderColor: C.border, opacity: variant === 'trash' ? 0.85 : 1 }}
    >
      <div className="h-1" style={{ background: accentColor }} />
      <div className="p-4 space-y-2.5">
        {/* Header */}
        <div className="flex items-start gap-2.5">
          <div className="h-8 w-8 shrink-0 rounded-lg flex items-center justify-center" style={{ background: accent.bg }}>
            <Icon className="h-4 w-4" style={{ color: accent.text }} strokeWidth={1.8} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[13px] font-semibold leading-tight line-clamp-1" style={{ color: C.ink }}>
              {document.nom}
            </p>
            <p className="text-[11px] mt-0.5 truncate text-muted-foreground">{document.nomFichier}</p>
            {uploaderName && !isUploader && (
              <p className="text-[11px] text-muted-foreground">Ajouté par {uploaderName}</p>
            )}
          </div>
          {variant === 'normal' && (
            <DocumentLocationsPopover
              document={document}
              monumentNames={monumentNames}
              dossiersById={dossiersById}
            />
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={stop}>
              <button className="shrink-0 p-1 rounded-md transition-colors hover:bg-black/[0.04] opacity-0 group-hover:opacity-100">
                <MoreVertical className="h-3.5 w-3.5 text-muted-foreground" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" onClick={stop}>
              {variant === 'normal' ? (
                <>
                  <DropdownMenuItem onClick={() => onPreview(document)}>
                    <Eye className="h-3.5 w-3.5 mr-2" />Aperçu
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => onAddToProject(document)}>
                    <FolderPlus className="h-3.5 w-3.5 mr-2" />Ajouter à un projet
                  </DropdownMenuItem>
                  {onRename && canModify && (
                    <DropdownMenuItem onClick={() => onRename(document)}>
                      <Pencil className="h-3.5 w-3.5 mr-2" />Renommer
                    </DropdownMenuItem>
                  )}
                  {/* Auteur : supprimer (→ corbeille). Responsable non-auteur : retirer du projet de la section. */}
                  {isUploader ? (
                    <DropdownMenuItem className="text-destructive" onClick={() => onTrash(document)}>
                      <Trash2 className="h-3.5 w-3.5 mr-2" />Supprimer
                    </DropdownMenuItem>
                  ) : (
                    canModify && sectionMonumentId && (
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => onRemoveFromProject(document, sectionMonumentId)}
                      >
                        <FolderMinus className="h-3.5 w-3.5 mr-2" />
                        Retirer de {monumentNames[sectionMonumentId] ?? 'ce projet'}
                      </DropdownMenuItem>
                    )
                  )}
                </>
              ) : (
                <>
                  <DropdownMenuItem onClick={() => onRestore(document)}>
                    <RotateCcw className="h-3.5 w-3.5 mr-2" />Restaurer
                  </DropdownMenuItem>
                  <DropdownMenuItem className="text-destructive" onClick={() => onDeletePermanent(document)}>
                    <Trash2 className="h-3.5 w-3.5 mr-2" />Supprimer définitivement
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Meta */}
        <div className="flex flex-wrap items-center gap-2">
          <Badge className="text-[10px] font-semibold border-0 px-1.5 py-0.5" style={{ background: accent.bg, color: accent.text }}>
            {typeLabel(document.type)}
          </Badge>
          <span className="text-[11px] text-muted-foreground">{formatFileSize(document.tailleFichier)}</span>
          {restricted && (
            <span
              className="inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium"
              style={{ background: C.paleBlue, color: C.blue }}
              title={VISIBILITY_META[document.visibility].help}
            >
              <Lock className="h-2.5 w-2.5" strokeWidth={2.2} />Accès restreint
            </span>
          )}
        </div>

        {/* Repère multi-projets */}
        {variant === 'normal' && multiProject && (
          <p className="text-[11px] text-muted-foreground">
            Aussi dans {document.monumentIds.length - 1} autre{document.monumentIds.length - 1 > 1 ? 's' : ''} projet{document.monumentIds.length - 1 > 1 ? 's' : ''}
          </p>
        )}
      </div>
    </div>
  );
}

