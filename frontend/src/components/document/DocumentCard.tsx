import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  IconAjouterDossier, IconModifier, IconSupprimer, IconProtection, IconDossierOuvert,
} from '@/components/icons';
import { Input } from '@/components/ui/input';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { canDeleteDocument } from '@/lib/project-permissions';
import { canEditVisibility } from '@/lib/document-visibility';
import { DocumentCardView, type DocMenuAction } from '@/components/document/DocumentCardView';
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

export function DocumentCard({
  document, dossierNames, onClick, onRename, onDelete, onAddToProject, myRole, uploaderName, onDocumentUpdated,
}: DocumentCardProps) {
  const { t } = useTranslation(['documents', 'common']);
  const currentUserId = useAuthStore((s) => s.user?.id);
  const isUploader = document.userId === currentUserId;
  const canModify = canDeleteDocument(isUploader, myRole);
  const canManageAccess = canEditVisibility(isUploader, myRole);

  const [accessOpen, setAccessOpen] = useState(false);
  const [renameOpen, setRenameOpen] = useState(false);
  const [newName, setNewName] = useState(document.nom);
  const [loading, setLoading] = useState(false);

  const linkedDossiers = dossierNames
    ? document.dossiersUtilises.map((id) => dossierNames[id]).filter(Boolean)
    : [];

  const handleRename = async () => {
    if (!onRename || !newName.trim() || newName === document.nom) { setRenameOpen(false); return; }
    setLoading(true);
    try { await onRename(document.id, newName.trim()); setRenameOpen(false); }
    finally { setLoading(false); }
  };

  const handleDelete = async () => {
    if (!onDelete) return;
    if (!confirm(t('DocumentCard.confirmSupprimer', { nom: document.nom }))) return;
    await onDelete(document.id);
  };

  const menuActions: DocMenuAction[] = [
    ...(onAddToProject
      ? [{ label: t('commun.ajouterAMonument'), icon: IconAjouterDossier, onClick: () => onAddToProject(document) }]
      : []),
    ...(canManageAccess
      ? [{ label: t('commun.gererAcces'), icon: IconProtection, onClick: () => setAccessOpen(true) }]
      : []),
    ...(onRename && canModify
      ? [{ label: t('commun.renommer'), icon: IconModifier, onClick: () => { setNewName(document.nom); setRenameOpen(true); } }]
      : []),
    ...(onDelete && canModify
      ? [{ label: t('common:actions.supprimer'), icon: IconSupprimer, onClick: handleDelete, destructive: true }]
      : []),
  ];

  return (
    <>
      <DocumentCardView
        document={document}
        onPreview={() => onClick?.()}
        uploaderName={uploaderName}
        menuActions={menuActions}
        footer={
          linkedDossiers.length > 0 ? (
            <span className="inline-flex items-center gap-1.5" title={t('DocumentCard.dossiersUtilisant')}>
              <IconDossierOuvert className="h-3.5 w-3.5" strokeWidth={1.8} />
              {linkedDossiers.length === 1
                ? linkedDossiers[0]
                : t('commun.utiliseDans', { count: linkedDossiers.length })}
            </span>
          ) : document.dossiersUtilises.length > 0 ? (
            <span className="inline-flex items-center gap-1.5">
              <IconDossierOuvert className="h-3.5 w-3.5" strokeWidth={1.8} />
              {t('commun.utiliseDans', { count: document.dossiersUtilises.length })}
            </span>
          ) : undefined
        }
      />

      <ManageDocumentAccessDialog
        document={document}
        myRole={myRole ?? null}
        open={accessOpen}
        onOpenChange={setAccessOpen}
        onSaved={onDocumentUpdated}
      />

      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent className="sm:max-w-sm" onClick={(e) => e.stopPropagation()}>
          <DialogHeader><DialogTitle>{t('DocumentCard.renommerTitre')}</DialogTitle></DialogHeader>
          <Input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleRename(); }}
            autoFocus
            className="h-10 text-[16px] bg-card border-border focus:border-primary focus:ring-primary/10"
          />
          <DialogFooter>
            <button onClick={() => setRenameOpen(false)} disabled={loading} className="px-4 py-2 text-[15px] font-medium border border-border rounded-lg text-muted-foreground hover:bg-muted transition-colors">
              {t('common:actions.annuler')}
            </button>
            <button onClick={handleRename} disabled={!newName.trim() || loading} className="px-4 py-2 text-[15px] font-semibold text-primary-foreground bg-primary rounded-lg disabled:opacity-50 hover:shadow-md transition-all">
              {loading ? t('DocumentCard.enregistrement') : t('common:actions.enregistrer')}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
