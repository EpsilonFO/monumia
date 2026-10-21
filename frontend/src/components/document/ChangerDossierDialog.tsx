import { useEffect, useState } from 'react';
import { Dialog as DialogPrimitive } from 'radix-ui';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { Picto } from '@/components/shared/ecrans/Picto';
import { TYPES_DOSSIERS, dossierLabel } from '@/lib/document-type-meta';
import { useDocumentStore } from '@/stores/useDocumentStore';
import type { Document, DocumentType } from '@/types';
import './documents.css';

interface ChangerDossierDialogProps {
  /** Les documents à ranger ; vide ou nul : fermée. */
  documents: Document[];
  onOpenChange: (open: boolean) => void;
  /** Après l'enregistrement, pour relire une liste locale. */
  onDeplace?: () => void;
}

/**
 * « Changer de dossier » (menu ⋮ d'un document, et « Déplacer » de la barre de
 * sélection) : un dossier n'étant qu'un type, déplacer = changer le type. Les
 * documents reçus sont déjà ceux qu'on a le droit de modifier (cf.
 * `repartirSelection`) : le serveur refuserait les autres.
 */
export function ChangerDossierDialog({ documents, onOpenChange, onDeplace }: ChangerDossierDialogProps) {
  const { t } = useTranslation(['documents', 'common']);
  const updateDocument = useDocumentStore((s) => s.updateDocument);
  const open = documents.length > 0;
  const [type, setType] = useState<DocumentType | ''>('');
  const [loading, setLoading] = useState(false);

  // Un seul document : son dossier actuel est présélectionné.
  useEffect(() => {
    if (open) setType(documents.length === 1 ? documents[0].type : '');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const deplacer = async () => {
    if (!type) return;
    setLoading(true);
    let ok = 0;
    for (const d of documents) {
      if (d.type === type) { ok += 1; continue; }
      try {
        await updateDocument(d.id, { type });
        ok += 1;
      } catch (err) {
        toast.error(t('commun.erreurDocument', {
          nom: d.nom,
          message: err instanceof Error ? err.message : t('ChangerDossierDialog.deplacementImpossible'),
        }));
      }
    }
    setLoading(false);
    if (ok > 0) {
      toast.success(ok > 1
        ? t('commun.rangesDansDossier', { nombre: ok, dossier: dossierLabel(type) })
        : t('commun.rangeDansDossier', { dossier: dossierLabel(type) }));
    }
    onDeplace?.();
    onOpenChange(false);
  };

  const titre = documents.length > 1
    ? t('ChangerDossierDialog.titrePlusieurs', { nombre: documents.length })
    : t('ChangerDossierDialog.titre');

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(o) => { if (!o && !loading) onOpenChange(false); }}>
      <DialogPrimitive.Portal>
        <div className="ec">
          <DialogPrimitive.Overlay className="dov">
            <DialogPrimitive.Content className="dmodal" aria-describedby={undefined}>
              <div className="m-h">
                <DialogPrimitive.Title asChild><h2>{titre}</h2></DialogPrimitive.Title>
                <DialogPrimitive.Close asChild>
                  <button className="x" type="button" aria-label={t('common:actions.fermer')} disabled={loading}>
                    <Picto nom="croix" />
                  </button>
                </DialogPrimitive.Close>
              </div>
              {documents.length === 1 && <p className="m-sub">{documents[0].nom}</p>}
              <div className="fld">
                <span className="lb">{t('commun.questionDossier')}</span>
                <div className="tps">
                  {TYPES_DOSSIERS.map((tp) => (
                    <button key={tp} type="button" className="tp" aria-pressed={type === tp} onClick={() => setType(tp)}>
                      {dossierLabel(tp)}
                    </button>
                  ))}
                </div>
              </div>
              <div className="m-f">
                <span className="hint">{loading ? t('ChangerDossierDialog.deplacement') : ''}</span>
                <button className="ghost" type="button" onClick={() => onOpenChange(false)} disabled={loading}>
                  {t('common:actions.annuler')}
                </button>
                <button className="btn b-orange" type="button" disabled={!type || loading} onClick={deplacer}>
                  {t('commun.deplacer')}
                </button>
              </div>
            </DialogPrimitive.Content>
          </DialogPrimitive.Overlay>
        </div>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
