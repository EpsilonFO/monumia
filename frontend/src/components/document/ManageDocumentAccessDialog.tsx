import { useEffect, useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { IconVoir } from '@/components/icons';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { MemberAvatar } from '@/components/sharing/MemberAvatar';
import { DocumentVisibilityField, type DocumentVisibilityValue } from './DocumentVisibilityField';
import { whoCanView } from '@/lib/document-visibility';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { sharingService } from '@/services/sharing.service';
import { toast } from 'sonner';
import type { Document, ProjectMember, ProjectRole } from '@/types';

interface Props {
  document: Document;
  myRole: ProjectRole | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Appelé après une mise à jour réussie (pour rafraîchir une liste locale). */
  onSaved?: () => void;
}

export function ManageDocumentAccessDialog({ document, myRole, open, onOpenChange, onSaved }: Props) {
  const updateDocument = useDocumentStore((s) => s.updateDocument);
  // Visibilité scopée au monument principal du document (v1 : monumentIds[0]).
  const monumentId = document.monumentIds[0];
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [value, setValue] = useState<DocumentVisibilityValue>({
    visibility: document.visibility,
    allowedUserIds: document.allowedUserIds,
  });
  const [saving, setSaving] = useState(false);

  // Aperçu « qui a accès », recalculé en direct selon la sélection en cours.
  const viewers = useMemo(() => {
    const ids = new Set(whoCanView(members, value.visibility, value.allowedUserIds, document.userId));
    return members.filter((m) => ids.has(m.userId));
  }, [members, value.visibility, value.allowedUserIds, document.userId]);

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
      onSaved?.();
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

        {members.length > 0 && (
          <div className="rounded-lg border px-3 py-2.5 border-border">
            <p className="flex items-center gap-1.5 text-[12px] font-semibold text-foreground">
              <IconVoir className="h-3.5 w-3.5" strokeWidth={1.8} />
              Peuvent voir ce document ({viewers.length})
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {viewers.map((m, i) => (
                <span
                  key={m.userId}
                  className="inline-flex items-center gap-1.5 rounded-full border border-border px-1.5 py-0.5 text-[12px] text-foreground"
                >
                  <MemberAvatar person={m} size="sm" colorIndex={i} />
                  {m.prenom} {m.nom}
                </span>
              ))}
            </div>
          </div>
        )}

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
