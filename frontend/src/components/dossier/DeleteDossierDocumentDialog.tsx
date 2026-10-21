import { useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { Loader2 } from 'lucide-react';
import { IconRetirerDossier, IconSupprimer } from '@/components/icons';
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
  const { t } = useTranslation(['dossier', 'common']);
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
          <DialogTitle>{t('DeleteDossierDocumentDialog.titre')}</DialogTitle>
          <DialogDescription>
            {itemLabel
              ? (
                <Trans
                  t={t}
                  i18nKey="DeleteDossierDocumentDialog.questionPiece"
                  values={{ piece: itemLabel }}
                  components={{ piece: <span className="font-medium" /> }}
                />
              )
              : t('DeleteDossierDocumentDialog.question')}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <button
            type="button"
            disabled={!!busyScope}
            onClick={() => handle('dossier')}
            className="w-full flex items-start gap-3 p-3 text-left rounded-lg border border-border hover:bg-muted transition-colors disabled:opacity-60"
          >
            {busyScope === 'dossier' ? (
              <Loader2 className="h-5 w-5 shrink-0 mt-0.5 animate-spin text-muted-foreground" />
            ) : (
              <IconRetirerDossier className="h-5 w-5 shrink-0 mt-0.5 text-primary" />
            )}
            <div>
              <p className="text-sm font-medium">{t('DeleteDossierDocumentDialog.retirerDossier')}</p>
              <p className="text-xs text-muted-foreground">
                {t('DeleteDossierDocumentDialog.retirerDossierTexte')}
              </p>
            </div>
          </button>

          <button
            type="button"
            disabled={!!busyScope}
            onClick={() => handle('everywhere')}
            className="w-full flex items-start gap-3 p-3 text-left rounded-lg border border-destructive/20 hover:bg-destructive-muted transition-colors disabled:opacity-60"
          >
            {busyScope === 'everywhere' ? (
              <Loader2 className="h-5 w-5 shrink-0 mt-0.5 animate-spin text-destructive" />
            ) : (
              <IconSupprimer className="h-5 w-5 shrink-0 mt-0.5 text-destructive" />
            )}
            <div>
              <p className="text-sm font-medium text-destructive">{t('DeleteDossierDocumentDialog.supprimerPartout')}</p>
              <p className="text-xs text-destructive/80">
                {t('DeleteDossierDocumentDialog.supprimerPartoutTexte')}
              </p>
            </div>
          </button>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={!!busyScope}>
            {t('common:actions.annuler')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
