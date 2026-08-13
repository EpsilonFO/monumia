import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { IconSucces, IconAttention, IconRafraichir, IconDocument } from '@/components/icons';
import { DocumentPreviewBody, useSignedUrl } from '@/components/document/DocumentPreviewDialog';
import { documentService } from '@/services/document.service';
import { C, SERIF } from '@/lib/brand';
import type { ChecklistItem, Document } from '@/types';

/**
 * Vérification guidée des pièces reprises automatiquement.
 *
 * Le public de Monumia — propriétaires de patrimoine souvent âgés, élus de
 * petites communes — ne cherche pas les boutons : il faut aller à lui. Ce
 * parcours s'ouvre donc tout seul quand un dossier contient des pièces
 * reprises, explique ce qui s'est passé en français courant, puis montre les
 * documents UN PAR UN, en grand, avec une seule question à la fois et deux
 * réponses possibles. Pas de jargon, pas de choix simultanés, pas d'icône à
 * deviner.
 *
 * Chaque écran ne fait qu'une chose : l'introduction explique, l'étape montre
 * un document et pose sa question, la conclusion récapitule. Fermer la fenêtre
 * n'est jamais grave — les pièces restent « à vérifier » dans la liste, et la
 * bannière du dossier permet de reprendre la vérification à tout moment.
 */

interface ReprisesReviewDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Les pièces à vérifier, figées à l'ouverture (l'ordre ne bouge pas en cours de route). */
  items: ChecklistItem[];
  /** Confirme la pièce (déjà tolérant aux erreurs : il affiche ses propres toasts). */
  onConfirm: (item: ChecklistItem) => Promise<void>;
  /** Rejette la pièce (idem). */
  onReject: (item: ChecklistItem) => Promise<void>;
}

/** Aperçu d'un document dont on ne connaît que l'id : résolution puis rendu. */
function ApercuDocument({ documentId, onDocument }: { documentId: string; onDocument: (d: Document | null) => void }) {
  const [doc, setDoc] = useState<Document | null>(null);
  const [erreur, setErreur] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setDoc(null);
    setErreur(false);
    documentService.getById(documentId).then(
      (d) => { if (!cancelled) { setDoc(d); onDocument(d); } },
      () => { if (!cancelled) { setErreur(true); onDocument(null); } },
    );
    return () => { cancelled = true; };
  }, [documentId]); // eslint-disable-line react-hooks/exhaustive-deps

  const { signedUrl, loading, error } = useSignedUrl(doc, !!doc);

  if (erreur) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-muted-foreground p-6 text-center">
        <IconDocument className="h-10 w-10 text-muted-foreground/50" />
        <p className="text-[15px]">
          L’aperçu n’est pas disponible, mais le document est bien là.
        </p>
      </div>
    );
  }
  if (!doc) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }
  return <DocumentPreviewBody document={doc} signedUrl={signedUrl} loading={loading} error={error} />;
}

export function ReprisesReviewDialog({ open, onOpenChange, items, onConfirm, onReject }: ReprisesReviewDialogProps) {
  // 0 = introduction, 1..n = documents, n+1 = conclusion.
  const [etape, setEtape] = useState(0);
  const [action, setAction] = useState<'confirm' | 'reject' | null>(null);
  const [confirmees, setConfirmees] = useState(0);
  const [docCourant, setDocCourant] = useState<Document | null>(null);

  useEffect(() => {
    if (open) { setEtape(0); setConfirmees(0); setDocCourant(null); }
  }, [open]);

  const total = items.length;
  const index = etape - 1; // index du document affiché (étapes 1..n)
  const item = index >= 0 && index < total ? items[index] : null;

  const suivant = () => { setDocCourant(null); setEtape((e) => e + 1); };

  const repondre = async (choix: 'confirm' | 'reject') => {
    if (!item || action) return;
    setAction(choix);
    try {
      if (choix === 'confirm') { await onConfirm(item); setConfirmees((c) => c + 1); }
      else await onReject(item);
    } finally {
      setAction(null);
      suivant();
    }
  };

  const boutonPlein =
    'inline-flex w-full items-center justify-center gap-2.5 rounded-xl px-5 h-13 min-h-12 text-[16px] font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-60';
  const boutonContour =
    'inline-flex w-full items-center justify-center gap-2.5 rounded-xl border px-5 h-13 min-h-12 text-[16px] font-semibold transition-colors hover:bg-muted disabled:opacity-60';

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!action) onOpenChange(o); }}>
      <DialogContent className="sm:max-w-2xl max-h-[92vh] flex flex-col gap-0 p-0 overflow-hidden">

        {/* ── Introduction ─────────────────────────────────────────────── */}
        {etape === 0 && (
          <div className="flex flex-col items-center text-center px-6 sm:px-10 py-10 overflow-y-auto">
            <span
              className="flex h-14 w-14 items-center justify-center rounded-full"
              style={{ background: C.paleBlue }}
            >
              <IconRafraichir className="h-7 w-7" style={{ color: C.blue }} />
            </span>
            <DialogTitle asChild>
              <h2 className="mt-5 text-[24px] leading-snug" style={{ fontFamily: SERIF, color: C.ink }}>
                {total === 1 ? 'Un document déjà prêt' : `${total} documents déjà prêts`}
              </h2>
            </DialogTitle>
            <p className="mt-3 max-w-md text-[15.5px] leading-relaxed" style={{ color: C.grayFg }}>
              Vous {total === 1 ? 'avez déjà fourni ce document' : 'aviez déjà fourni ces documents'} lors
              d’une demande précédente. Nous {total === 1 ? 'l’avons ajouté' : 'les avons ajoutés'} à ce
              dossier pour vous éviter de {total === 1 ? 'le' : 'les'} chercher à nouveau.
            </p>

            <ul className="mt-6 w-full max-w-md space-y-2 text-left">
              {items.map((i) => (
                <li
                  key={i.id}
                  className="flex items-start gap-2.5 rounded-lg border px-3.5 py-2.5 text-[14.5px]"
                  style={{ borderColor: C.border, color: C.ink }}
                >
                  <IconDocument className="mt-0.5 h-4 w-4 shrink-0" style={{ color: C.blue }} />
                  {i.label}
                </li>
              ))}
            </ul>

            <p className="mt-6 max-w-md text-[15.5px] leading-relaxed" style={{ color: C.grayFg }}>
              Nous allons vous {total === 1 ? 'le' : 'les'} montrer{total > 1 ? ' un par un' : ''}. Vous
              n’avez qu’à dire si c’est bien le bon document.
            </p>

            <div className="mt-7 w-full max-w-md space-y-3">
              <button type="button" className={boutonPlein} style={{ background: C.blue }} onClick={suivant}>
                {total === 1 ? 'Voir le document' : 'Voir le premier document'}
              </button>
              <button
                type="button"
                onClick={() => onOpenChange(false)}
                className="w-full text-[14px] underline-offset-4 hover:underline"
                style={{ color: C.grayMuted }}
              >
                Plus tard — les documents resteront dans la liste
              </button>
            </div>
          </div>
        )}

        {/* ── Un document à la fois ────────────────────────────────────── */}
        {item && (
          <div className="flex min-h-0 flex-col overflow-y-auto">
            <div className="px-6 sm:px-8 pt-7 pb-4 text-center">
              <p className="text-[13px] font-medium uppercase tracking-wide" style={{ color: C.grayMuted }}>
                Document {etape} sur {total}
              </p>
              <DialogTitle asChild>
                <h2 className="mt-1.5 text-[21px] leading-snug" style={{ fontFamily: SERIF, color: C.ink }}>
                  {item.label}
                </h2>
              </DialogTitle>
              {docCourant && (
                <p className="mt-1 text-[14.5px]" style={{ color: C.grayFg }}>
                  Votre document&nbsp;: «&nbsp;{docCourant.nom}&nbsp;»
                </p>
              )}
            </div>

            <div
              className="mx-6 sm:mx-8 h-[38vh] min-h-[220px] shrink-0 overflow-hidden rounded-xl border bg-muted/30"
              style={{ borderColor: C.border }}
            >
              {item.documentId && (
                <ApercuDocument key={item.id} documentId={item.documentId} onDocument={setDocCourant} />
              )}
            </div>

            {item.perime && (
              <div
                className="mx-6 sm:mx-8 mt-4 flex items-start gap-2.5 rounded-lg border px-3.5 py-3 text-[14px]"
                style={{ borderColor: C.orangeVif, background: C.paleOrange, color: C.ink }}
              >
                <IconAttention className="mt-0.5 h-4.5 w-4.5 shrink-0" style={{ color: C.orange }} />
                Ce document a plus d’un an. Vérifiez qu’il est encore à jour avant de l’utiliser.
              </div>
            )}

            <div className="px-6 sm:px-8 py-6 space-y-3">
              <p className="text-center text-[16px] font-medium" style={{ color: C.ink }}>
                Est-ce bien le document qu’il faut pour ce dossier&nbsp;?
              </p>
              <button
                type="button"
                disabled={!!action}
                onClick={() => repondre('confirm')}
                className={boutonPlein}
                style={{ background: C.success }}
              >
                {action === 'confirm' ? <Loader2 className="h-5 w-5 animate-spin" /> : <IconSucces className="h-5 w-5" />}
                Oui, c’est le bon document
              </button>
              <button
                type="button"
                disabled={!!action}
                onClick={() => repondre('reject')}
                className={boutonContour}
                style={{ borderColor: C.border, color: C.ink }}
              >
                {action === 'reject' && <Loader2 className="h-5 w-5 animate-spin" />}
                Non, ce n’est pas le bon
              </button>
              <button
                type="button"
                disabled={!!action}
                onClick={suivant}
                className="w-full text-[14px] underline-offset-4 hover:underline disabled:opacity-60"
                style={{ color: C.grayMuted }}
              >
                Je déciderai plus tard
              </button>
            </div>
          </div>
        )}

        {/* ── Conclusion ───────────────────────────────────────────────── */}
        {etape > total && (
          <div className="flex flex-col items-center px-6 sm:px-10 py-12 text-center">
            <span className="flex h-14 w-14 items-center justify-center rounded-full" style={{ background: C.successMuted }}>
              <IconSucces className="h-7 w-7" style={{ color: C.success }} />
            </span>
            <DialogTitle asChild>
              <h2 className="mt-5 text-[24px]" style={{ fontFamily: SERIF, color: C.ink }}>
                Vérification terminée
              </h2>
            </DialogTitle>
            <p className="mt-3 max-w-md text-[15.5px] leading-relaxed" style={{ color: C.grayFg }}>
              {confirmees === 0
                ? 'Aucun document n’a été confirmé pour l’instant.'
                : confirmees === 1
                  ? 'Un document a été ajouté à votre dossier.'
                  : `${confirmees} documents ont été ajoutés à votre dossier.`}
              {confirmees < total && (
                <> Les autres restent marqués «&nbsp;à vérifier&nbsp;» dans la liste des pièces — vous pourrez y revenir quand vous voudrez.</>
              )}
            </p>
            <button
              type="button"
              onClick={() => onOpenChange(false)}
              className={`mt-7 max-w-md ${boutonPlein}`}
              style={{ background: C.blue }}
            >
              Revenir au dossier
            </button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
