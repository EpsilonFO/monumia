import { useEffect, useState } from 'react';
import { Download, ExternalLink, FileWarning, Loader2 } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { formatFileSize } from '@/lib/format-utils';
import { documentService } from '@/services/document.service';
import type { Document } from '@/types';

interface DocumentPreviewDialogProps {
  document: Document | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const typeLabels: Record<string, string> = {
  photo: 'Photo',
  plan: 'Plan',
  devis: 'Devis',
  facture: 'Facture',
  attestation: 'Attestation',
  extrait_cadastral: 'Extrait cadastral',
  cerfa: 'CERFA',
  arrete: 'Arrêté',
  diagnostic: 'Diagnostic',
  rapport: 'Rapport',
  correspondance: 'Correspondance',
  autre: 'Autre',
};

// HEIC/HEIF are not natively supported by any browser — exclude them from 'image'.
const BROWSER_IMAGE_MIME = new Set([
  'image/jpeg', 'image/png', 'image/gif', 'image/webp',
  'image/svg+xml', 'image/bmp', 'image/avif',
]);

const OFFICE_MIME_TYPES = new Set([
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.oasis.opendocument.text',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.oasis.opendocument.spreadsheet',
  'application/vnd.ms-powerpoint',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
]);

const TEXT_MIME_TYPES = new Set(['text/plain', 'text/csv']);

type PreviewType = 'image' | 'pdf' | 'office' | 'text' | 'none';

function getPreviewType(mimeType: string): PreviewType {
  if (BROWSER_IMAGE_MIME.has(mimeType)) return 'image';
  if (mimeType === 'application/pdf') return 'pdf';
  if (OFFICE_MIME_TYPES.has(mimeType)) return 'office';
  if (TEXT_MIME_TYPES.has(mimeType)) return 'text';
  return 'none';
}

function isLocalUrl(url: string): boolean {
  return url.includes('localhost') || url.includes('127.0.0.1');
}

async function downloadFile(url: string, filename: string) {
  const res = await fetch(url);
  const blob = await res.blob();
  const blobUrl = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement('a'), { href: blobUrl, download: filename });
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(blobUrl);
}

// ── Sub-components ────────────────────────────────────────────────────────────

function ImagePreview({ url, alt }: { url: string; alt: string }) {
  const [error, setError] = useState(false);

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-muted-foreground">
        <FileWarning className="h-12 w-12 text-muted-foreground/50" />
        <p className="text-sm">Impossible de charger l'image.</p>
        <Button variant="outline" size="sm" onClick={() => downloadFile(url, 'image')}>
          <Download className="h-4 w-4 mr-1.5" />
          Télécharger
        </Button>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center p-6 h-full">
      <img
        src={url}
        alt={alt}
        className="max-w-full max-h-full object-contain rounded"
        onError={() => setError(true)}
      />
    </div>
  );
}

function TextPreview({ url }: { url: string }) {
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(url)
      .then((r) => r.text())
      .then((t) => { if (!cancelled) setContent(t); })
      .catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [url]);

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-muted-foreground">
        <FileWarning className="h-12 w-12 text-muted-foreground/50" />
        <p className="text-sm">Impossible de charger le fichier texte.</p>
      </div>
    );
  }

  if (content === null) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <pre className="w-full h-full p-6 text-xs font-mono whitespace-pre-wrap break-words overflow-auto text-foreground">
      {content}
    </pre>
  );
}

function OfficePreview({ url, title, filename }: { url: string; title: string; filename: string }) {
  if (isLocalUrl(url)) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-muted-foreground">
        <FileWarning className="h-12 w-12 text-muted-foreground/50" />
        <p className="text-sm font-medium">Prévisualisation Office indisponible en local</p>
        <p className="text-xs text-center max-w-xs">
          Le visualiseur Word/Excel nécessite une URL accessible depuis Internet.
          Il fonctionnera normalement en production.
        </p>
        <Button variant="outline" size="sm" onClick={() => downloadFile(url, filename)}>
          <Download className="h-4 w-4 mr-1.5" />
          Télécharger pour ouvrir localement
        </Button>
      </div>
    );
  }

  return (
    <iframe
      src={`https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(url)}`}
      className="w-full h-full border-0"
      title={title}
    />
  );
}

// ── Main dialog ───────────────────────────────────────────────────────────────

export function DocumentPreviewDialog({ document, open, onOpenChange }: DocumentPreviewDialogProps) {
  const [signedUrl, setSignedUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !document) {
      setSignedUrl(null);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    documentService.getSignedUrl(document.url).then(
      (url) => { if (!cancelled) { setSignedUrl(url); setLoading(false); } },
      (err) => { if (!cancelled) { setError(err.message); setLoading(false); } },
    );

    return () => { cancelled = true; };
  }, [open, document?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!document) return null;

  const previewType = getPreviewType(document.mimeType);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-5xl h-[90vh] flex flex-col p-0 gap-0">
        <DialogHeader className="px-6 pt-6 pb-4 border-b shrink-0">
          <div className="flex items-start justify-between gap-4 pr-8">
            <div className="min-w-0">
              <DialogTitle className="truncate">{document.nom}</DialogTitle>
              <div className="flex items-center gap-2 mt-1.5">
                <Badge variant="outline" className="text-xs">
                  {typeLabels[document.type] ?? document.type}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {formatFileSize(document.tailleFichier)}
                </span>
                <span className="text-xs text-muted-foreground truncate">
                  {document.nomFichier}
                </span>
              </div>
            </div>
            {signedUrl && (
              <div className="flex gap-2 shrink-0">
                <Button variant="outline" size="sm" onClick={() => downloadFile(signedUrl, document.nomFichier)}>
                  <Download className="h-4 w-4 mr-1.5" />
                  Télécharger
                </Button>
                <Button variant="outline" size="sm" asChild>
                  <a href={signedUrl} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="h-4 w-4 mr-1.5" />
                    Ouvrir
                  </a>
                </Button>
              </div>
            )}
          </div>
        </DialogHeader>

        <div className="flex-1 min-h-0 overflow-auto bg-muted/30">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center h-full gap-4 text-muted-foreground">
              <FileWarning className="h-12 w-12 text-muted-foreground/50" />
              <p className="text-sm">Impossible de charger le document.</p>
              <p className="text-xs">{error}</p>
            </div>
          ) : signedUrl ? (
            <>
              {previewType === 'image' && (
                <ImagePreview url={signedUrl} alt={document.nom} />
              )}
              {previewType === 'pdf' && (
                <object data={signedUrl} type="application/pdf" className="w-full h-full">
                  <div className="flex flex-col items-center justify-center h-full gap-4 text-muted-foreground">
                    <FileWarning className="h-12 w-12 text-muted-foreground/50" />
                    <p className="text-sm">Impossible d'afficher le PDF dans le navigateur.</p>
                    <Button variant="outline" size="sm" asChild>
                      <a href={signedUrl} target="_blank" rel="noopener noreferrer">
                        Ouvrir le PDF
                      </a>
                    </Button>
                  </div>
                </object>
              )}
              {previewType === 'office' && (
                <OfficePreview url={signedUrl} title={document.nom} filename={document.nomFichier} />
              )}
              {previewType === 'text' && (
                <TextPreview url={signedUrl} />
              )}
              {previewType === 'none' && (
                <div className="flex flex-col items-center justify-center h-full gap-4 text-muted-foreground">
                  <FileWarning className="h-12 w-12 text-muted-foreground/50" />
                  <p className="text-sm font-medium">Format non prévisualisable</p>
                  <p className="text-xs">
                    {document.mimeType.includes('heic') || document.mimeType.includes('heif')
                      ? 'Le format HEIC/HEIF n\'est pas supporté par les navigateurs. Téléchargez le fichier pour l\'ouvrir.'
                      : 'Aperçu non disponible pour ce type de fichier.'}
                  </p>
                  <Button variant="outline" size="sm" onClick={() => downloadFile(signedUrl!, document.nomFichier)}>
                    <Download className="h-4 w-4 mr-1.5" />
                    Télécharger
                  </Button>
                </div>
              )}
            </>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
