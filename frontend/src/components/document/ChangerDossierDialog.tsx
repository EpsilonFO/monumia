import { useEffect, useState } from 'react';
import { Dialog as DialogPrimitive } from 'radix-ui';
import { toast } from 'sonner';
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
        toast.error(`${d.nom} : ${err instanceof Error ? err.message : 'déplacement impossible'}`);
      }
    }
    setLoading(false);
    if (ok > 0) {
      toast.success(ok > 1
        ? `${ok} documents rangés dans le dossier ${dossierLabel(type)}.`
        : `Rangé dans le dossier ${dossierLabel(type)}.`);
    }
    onDeplace?.();
    onOpenChange(false);
  };

  const titre = documents.length > 1 ? `Déplacer ${documents.length} documents` : 'Changer de dossier';

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(o) => { if (!o && !loading) onOpenChange(false); }}>
      <DialogPrimitive.Portal>
        <div className="ec">
          <DialogPrimitive.Overlay className="dov">
            <DialogPrimitive.Content className="dmodal" aria-describedby={undefined}>
              <div className="m-h">
                <DialogPrimitive.Title asChild><h2>{titre}</h2></DialogPrimitive.Title>
                <DialogPrimitive.Close asChild>
                  <button className="x" type="button" aria-label="Fermer" disabled={loading}>
                    <Picto nom="croix" />
                  </button>
                </DialogPrimitive.Close>
              </div>
              {documents.length === 1 && <p className="m-sub">{documents[0].nom}</p>}
              <div className="fld">
                <span className="lb">Dans quel dossier le ranger ?</span>
                <div className="tps">
                  {TYPES_DOSSIERS.map((t) => (
                    <button key={t} type="button" className="tp" aria-pressed={type === t} onClick={() => setType(t)}>
                      {dossierLabel(t)}
                    </button>
                  ))}
                </div>
              </div>
              <div className="m-f">
                <span className="hint">{loading ? 'Déplacement…' : ''}</span>
                <button className="ghost" type="button" onClick={() => onOpenChange(false)} disabled={loading}>
                  Annuler
                </button>
                <button className="btn b-orange" type="button" disabled={!type || loading} onClick={deplacer}>
                  Déplacer
                </button>
              </div>
            </DialogPrimitive.Content>
          </DialogPrimitive.Overlay>
        </div>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
