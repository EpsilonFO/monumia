import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { IconSucces, IconAttention, IconRafraichir, IconDocument } from '@/components/icons';
import { DocumentPreviewBody, useSignedUrl } from '@/components/document/DocumentPreviewDialog';
import { documentService } from '@/services/document.service';
import { C, SERIF } from '@/lib/brand';
import type { ChecklistItem, Document } from '@/types';

/**
 * Vérification guidée des pièces reprises automatiquement.
 *
 * Le public de Monumia — propriétaires de patrimoine souvent âgés, élus de
 * petites communes — ne cherche pas les boutons : il faut aller à lui. Cette
 * fenêtre s'ouvre donc toute seule quand un dossier contient des pièces
 * reprises et va droit au but : le premier document s'affiche immédiatement,
 * en grand, avec une phrase d'explication, une seule question et deux réponses
 * possibles. Pas d'écran préparatoire, pas de jargon, pas de choix simultanés.
 *
 * Fermer la fenêtre n'est jamais grave — les pièces restent « à vérifier »
 * dans la liste, et la bannière du dossier permet de reprendre la
 * vérification à tout moment.
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
        <p className="text-sm">L’aperçu n’est pas disponible, mais le document est bien là.</p>
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
  // 0..n-1 = documents, n = conclusion. Pas d'écran préparatoire : le premier
  // document EST l'explication — on montre plutôt que d'annoncer qu'on va montrer.
  const [etape, setEtape] = useState(0);
  const [action, setAction] = useState<'confirm' | 'reject' | null>(null);
  const [confirmees, setConfirmees] = useState(0);
  const [docCourant, setDocCourant] = useState<Document | null>(null);

  useEffect(() => {
    if (open) { setEtape(0); setConfirmees(0); setDocCourant(null); }
  }, [open]);

  const total = items.length;
  const item = etape < total ? items[etape] : null;

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

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!action) onOpenChange(o); }}>
      <DialogContent className="sm:max-w-2xl max-h-[92vh] flex flex-col gap-0 p-0 overflow-hidden">

        {/* ── Un document à la fois ────────────────────────────────────── */}
        {item && (
          <div className="flex min-h-0 flex-col overflow-y-auto">
            <DialogHeader className="px-6 pt-6 pb-4 border-b shrink-0 text-left">
              {total > 1 && (
                <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Document {etape + 1} sur {total}
                </p>
              )}
              <DialogTitle className="text-[19px] leading-snug font-normal" style={{ fontFamily: SERIF, color: C.ink }}>
                {item.label}
              </DialogTitle>
              {docCourant && (
                <p className="text-[13px] text-muted-foreground">
                  Votre document&nbsp;: «&nbsp;{docCourant.nom}&nbsp;»
                </p>
              )}
            </DialogHeader>

            {etape === 0 && (
              <div className="mx-6 mt-4 flex items-start gap-3 p-4 rounded-xl border" style={{ borderColor: C.border, background: C.paleBlue }}>
                <IconRafraichir className="h-5 w-5 shrink-0 mt-0.5" style={{ color: C.blue }} />
                <p className="text-[13px]" style={{ color: C.ink }}>
                  {total === 1
                    ? 'Vous aviez déjà fourni ce document lors d’une demande précédente. Nous l’avons ajouté à ce dossier — il ne reste qu’à vérifier que c’est le bon.'
                    : `Vous aviez déjà fourni ${total} documents lors de demandes précédentes. Nous les avons ajoutés à ce dossier — il ne reste qu’à vérifier, un par un, que ce sont les bons.`}
                </p>
              </div>
            )}

            <div className="mx-6 mt-4 h-[38vh] min-h-[220px] shrink-0 overflow-hidden rounded-xl border bg-muted/30" style={{ borderColor: C.border }}>
              {item.documentId && (
                <ApercuDocument key={item.id} documentId={item.documentId} onDocument={setDocCourant} />
              )}
            </div>

            {item.perime && (
              <div className="mx-6 mt-4 flex items-start gap-3 p-4 rounded-xl border" style={{ borderColor: C.orangeVif, background: C.paleOrange }}>
                <IconAttention className="h-5 w-5 shrink-0 mt-0.5" style={{ color: C.orange }} />
                <p className="text-[13px]" style={{ color: C.ink }}>
                  Ce document a plus d’un an. Vérifiez qu’il est encore à jour avant de l’utiliser.
                </p>
              </div>
            )}

            <div className="px-6 py-5 space-y-2.5">
              <p className="text-center text-[15px] font-medium" style={{ color: C.ink }}>
                Est-ce bien le document qu’il faut pour ce dossier&nbsp;?
              </p>
              <Button
                size="lg"
                disabled={!!action}
                onClick={() => repondre('confirm')}
                className="w-full h-11 text-[15px]"
              >
                {action === 'confirm' ? <Loader2 className="animate-spin" /> : <IconSucces />}
                Oui, c’est le bon document
              </Button>
              <Button
                variant="outline"
                size="lg"
                disabled={!!action}
                onClick={() => repondre('reject')}
                className="w-full h-11 text-[15px]"
              >
                {action === 'reject' && <Loader2 className="animate-spin" />}
                Non, ce n’est pas le bon
              </Button>
              <Button
                variant="ghost"
                disabled={!!action}
                onClick={suivant}
                className="w-full text-muted-foreground"
              >
                Je déciderai plus tard
              </Button>
            </div>
          </div>
        )}

        {/* ── Conclusion ───────────────────────────────────────────────── */}
        {!item && (
          <div className="flex flex-col items-center px-6 sm:px-10 py-12 text-center">
            <span className="flex h-14 w-14 items-center justify-center rounded-full bg-success-muted">
              <IconSucces className="h-7 w-7 text-success" />
            </span>
            <DialogTitle className="mt-5 text-[22px] font-normal" style={{ fontFamily: SERIF, color: C.ink }}>
              Vérification terminée
            </DialogTitle>
            <p className="mt-3 max-w-md text-[14.5px] leading-relaxed text-muted-foreground">
              {confirmees === 0
                ? 'Aucun document n’a été confirmé pour l’instant.'
                : confirmees === 1
                  ? 'Un document a été ajouté à votre dossier.'
                  : `${confirmees} documents ont été ajoutés à votre dossier.`}
              {confirmees < total && (
                <> Les autres restent marqués «&nbsp;à vérifier&nbsp;» dans la liste des pièces — vous pourrez y revenir quand vous voudrez.</>
              )}
            </p>
            <Button size="lg" onClick={() => onOpenChange(false)} className="mt-7 h-11 px-8 text-[15px]">
              Revenir au dossier
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
