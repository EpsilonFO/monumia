import { useEffect, useRef, useState } from 'react';
import { documentService } from '@/services/document.service';
import type { TextSource } from '@/lib/text-preview';

// Formats que le navigateur sait afficher directement (HEIC/HEIF exclus).
const BROWSER_IMAGE_MIME = new Set([
  'image/jpeg', 'image/png', 'image/gif', 'image/webp',
  'image/svg+xml', 'image/bmp', 'image/avif',
]);

const DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
const XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

export type DocPreview =
  | { kind: 'image'; url: string; fit: 'cover' | 'top' }
  | { kind: 'text'; text: string }
  | { kind: 'grid'; rows: string[][] }
  | null;

/** Détermine la source d'aperçu texte/bureautique (ou null). */
function textSourceOf(mimeType: string, fileName: string): TextSource | null {
  if (mimeType === 'text/csv' || /\.csv$/i.test(fileName)) return 'csv';
  if (mimeType === 'text/plain' || /\.txt$/i.test(fileName)) return 'txt';
  if (mimeType === DOCX_MIME || /\.docx$/i.test(fileName)) return 'docx';
  if (mimeType === XLSX_MIME || /\.xlsx$/i.test(fileName)) return 'xlsx';
  return null;
}

/**
 * Charge paresseusement (IntersectionObserver) un vrai aperçu de document :
 *   • image → l'image elle-même ; • PDF → 1re page rendue (pdfjs) ;
 *   • TXT/DOCX → texte enroulé ; • CSV/XLSX → petit tableau.
 * Le travail n'est déclenché qu'à l'approche du viewport. `preview = null` pour
 * tout ce qui n'a pas d'aperçu → la carte retombe sur le bandeau coloré.
 */
export function useDocumentThumbnail(
  documentId: string,
  mimeType: string,
  fileName = '',
  /** Faux : images et PDF seulement (les cartes de Mes documents, où un
   *  aperçu texte ne se lirait pas et coûterait un téléchargement complet). */
  { texte = true }: { texte?: boolean } = {},
) {
  const ref = useRef<HTMLElement>(null);
  const [preview, setPreview] = useState<DocPreview>(null);

  const isImage = BROWSER_IMAGE_MIME.has(mimeType);
  const isPdf = mimeType === 'application/pdf' || /\.pdf$/i.test(fileName);
  const textSource = texte ? textSourceOf(mimeType, fileName) : null;
  const previewable = isImage || isPdf || textSource !== null;

  useEffect(() => {
    if (!previewable || preview) return;
    const el = ref.current;
    if (!el) return;

    let cancelled = false;
    const io = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        io.disconnect();
        documentService.getSignedUrl(documentId).then(
          async (signed) => {
            if (cancelled) return;
            try {
              if (isImage) {
                setPreview({ kind: 'image', url: signed, fit: 'cover' });
              } else if (isPdf) {
                const { renderPdfThumbnail } = await import('@/lib/pdf-thumbnail');
                const dataUrl = await renderPdfThumbnail(signed);
                if (!cancelled && dataUrl) setPreview({ kind: 'image', url: dataUrl, fit: 'top' });
              } else if (textSource) {
                const { extractPreview } = await import('@/lib/text-preview');
                const data = await extractPreview(signed, textSource);
                if (!cancelled && data) setPreview(data);
              }
            } catch (e) {
              console.warn('[thumbnail] aperçu impossible', e);
            }
          },
          (e) => { console.warn('[thumbnail] URL signée impossible', e); },
        );
      },
      { rootMargin: '285px' },
    );
    io.observe(el);
    return () => { cancelled = true; io.disconnect(); };
  }, [documentId, previewable, isImage, isPdf, textSource, preview]);

  return { ref, preview };
}
