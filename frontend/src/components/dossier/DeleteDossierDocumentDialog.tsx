import { useState } from 'react';
import { FolderMinus, Loader2, Trash2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';

export type DeleteScope = 'dossier' | 'everywhere';

interface DeleteDossierDocumentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  itemLabel?: string;
  onConfirm: (scope: DeleteScope) => Promise<void>;
}

export function DeleteDossierDocumentDialog({
  open,
  onOpenChange,
  itemLabel,
  onConfirm,
}: DeleteDossierDocumentDialogProps) {
  const [busyScope, setBusyScope] = useState<DeleteScope | null>(null);

  const handle = async (scope: DeleteScope) => {
    setBusyScope(scope);
    try {
      await onConfirm(scope);
      onOpenChange(false);
    } finally {
      setBusyScope(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !busyScope && onOpenChange(o)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Supprimer le document</DialogTitle>
          <DialogDescription>
            {itemLabel
              ? <>Que souhaitez-vous faire du document rattaché à <span className="font-medium">« {itemLabel} »</span> ?</>
              : 'Que souhaitez-vous faire de ce document ?'}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <button
            type="button"
            disabled={!!busyScope}
            onClick={() => handle('dossier')}
            className="w-full flex items-start gap-3 p-3 text-left rounded-lg border border-[#E4E2DC] hover:bg-[#F8F7F4] transition-colors disabled:opacity-60"
          >
            {busyScope === 'dossier' ? (
              <Loader2 className="h-5 w-5 shrink-0 mt-0.5 animate-spin text-muted-foreground" />
            ) : (
              <FolderMinus className="h-5 w-5 shrink-0 mt-0.5 text-[#1A237E]" />
            )}
            <div>
              <p className="text-sm font-medium">Retirer du dossier uniquement</p>
              <p className="text-xs text-muted-foreground">
                Le document reste disponible dans l'onglet « Documents ».
              </p>
            </div>
          </button>

          <button
            type="button"
            disabled={!!busyScope}
            onClick={() => handle('everywhere')}
            className="w-full flex items-start gap-3 p-3 text-left rounded-lg border border-red-200 hover:bg-red-50 transition-colors disabled:opacity-60"
          >
            {busyScope === 'everywhere' ? (
              <Loader2 className="h-5 w-5 shrink-0 mt-0.5 animate-spin text-red-600" />
            ) : (
              <Trash2 className="h-5 w-5 shrink-0 mt-0.5 text-red-600" />
            )}
            <div>
              <p className="text-sm font-medium text-red-700">Supprimer partout</p>
              <p className="text-xs text-red-600/80">
                Retire le document de ce dossier et le supprime définitivement de la bibliothèque.
              </p>
            </div>
          </button>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={!!busyScope}>
            Annuler
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
