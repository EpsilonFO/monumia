import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { DocumentVisibilityField, type DocumentVisibilityValue } from './DocumentVisibilityField';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { sharingService } from '@/services/sharing.service';
import { toast } from 'sonner';
import type { Document, ProjectMember, ProjectRole } from '@/types';

interface Props {
  document: Document;
  myRole: ProjectRole | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ManageDocumentAccessDialog({ document, myRole, open, onOpenChange }: Props) {
  const updateDocument = useDocumentStore((s) => s.updateDocument);
  // Visibilité scoptée au projet principal du document (v1 : monumentIds[0]).
  const monumentId = document.monumentIds[0];
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [value, setValue] = useState<DocumentVisibilityValue>({
    visibility: document.visibility,
    allowedUserIds: document.allowedUserIds,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    // Les champs document (visibility, allowedUserIds) sont lus uniquement à l'ouverture —
    // intentionnel pour ne pas écraser la sélection en cours si le store se met à jour.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    setValue({ visibility: document.visibility, allowedUserIds: document.allowedUserIds });
    if (!monumentId) { setMembers([]); return; }
    let cancelled = false;
    sharingService
      .getMembers(monumentId)
      .then((r) => { if (!cancelled) setMembers(r.members); })
      .catch(() => { if (!cancelled) setMembers([]); });
    return () => { cancelled = true; };
  }, [open, monumentId]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateDocument(document.id, {
        visibility: value.visibility,
        allowedUserIds: value.allowedUserIds,
      });
      toast.success('Accès mis à jour');
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Échec de la mise à jour');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" onClick={(e) => e.stopPropagation()}>
        <DialogHeader>
          <DialogTitle>Gérer l'accès</DialogTitle>
        </DialogHeader>

        <DocumentVisibilityField
          value={value}
          onChange={setValue}
          currentUserRole={myRole}
          members={members}
        />

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
            Annuler
          </Button>
          <Button type="button" onClick={handleSave} disabled={saving}>
            {saving ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Enregistrement…</> : 'Enregistrer'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
