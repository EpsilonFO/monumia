import {
  IconAjouterDossier, IconSupprimer, IconRafraichir, IconRetirerDossier, IconModifier,
} from '@/components/icons';
import { canDeleteDocument } from '@/lib/project-permissions';
import { DocumentLocationsPopover } from '@/components/document/DocumentLocationsPopover';
import { DocumentCardView, type DocMenuAction } from '@/components/document/DocumentCardView';
import { useAuthStore } from '@/stores/useAuthStore';
import type { Document, ProjectRole } from '@/types';

interface DocumentTileProps {
  document: Document;
  /** Conservé pour compat d'appel ; la couleur d'ancrage vient désormais du type. */
  accentColor?: string;
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
  document, monumentNames, dossiersById, uploaderName, myRole,
  sectionMonumentId, variant = 'normal',
  onPreview, onAddToProject, onRename, onTrash, onRemoveFromProject, onRestore, onDeletePermanent,
}: DocumentTileProps) {
  const currentUserId = useAuthStore((s) => s.user?.id);
  const isUploader = document.userId === currentUserId;
  const canModify = canDeleteDocument(isUploader, myRole);

  const menuActions: DocMenuAction[] = variant === 'normal'
    ? [
        { label: 'Ajouter à un monument', icon: IconAjouterDossier, onClick: () => onAddToProject(document) },
        ...(onRename && canModify
          ? [{ label: 'Renommer', icon: IconModifier, onClick: () => onRename(document) }]
          : []),
        ...(isUploader
          ? [{ label: 'Supprimer', icon: IconSupprimer, onClick: () => onTrash(document), destructive: true }]
          : canModify && sectionMonumentId
            ? [{
                label: `Retirer de ${monumentNames[sectionMonumentId] ?? 'ce monument'}`,
                icon: IconRetirerDossier,
                onClick: () => onRemoveFromProject(document, sectionMonumentId),
                destructive: true,
              }]
            : []),
      ]
    : [
        { label: 'Restaurer', icon: IconRafraichir, onClick: () => onRestore(document) },
        { label: 'Supprimer définitivement', icon: IconSupprimer, onClick: () => onDeletePermanent(document), destructive: true },
      ];

  return (
    <DocumentCardView
      document={document}
      variant={variant}
      onPreview={() => onPreview(document)}
      canDownload={variant === 'normal'}
      uploaderName={!isUploader ? uploaderName : undefined}
      locations={variant === 'normal'
        ? <DocumentLocationsPopover document={document} monumentNames={monumentNames} dossiersById={dossiersById} labelled />
        : undefined}
      menuActions={menuActions}
    />
  );
}
