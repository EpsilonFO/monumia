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

const OFFICE_MIME_TYPES = new Set([
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.ms-powerpoint',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
]);

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

function getPreviewType(mimeType: string): 'image' | 'pdf' | 'office' | 'none' {
  if (mimeType.startsWith('image/')) return 'image';
  if (mimeType === 'application/pdf') return 'pdf';
  if (OFFICE_MIME_TYPES.has(mimeType)) return 'office';
  return 'none';
}

function ImagePreview({ url, alt }: { url: string; alt: string }) {
  const [error, setError] = useState(false);

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-muted-foreground">
        <FileWarning className="h-12 w-12 text-muted-foreground/50" />
        <p className="text-sm">Impossible de charger l'image.</p>
        <Button variant="outline" size="sm" asChild>
          <a href={url} target="_blank" rel="noopener noreferrer">
            <ExternalLink className="h-4 w-4 mr-1.5" />
            Ouvrir dans un nouvel onglet
          </a>
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
                <object
                  data={signedUrl}
                  type="application/pdf"
                  className="w-full h-full"
                >
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
                <iframe
                  src={`https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(signedUrl)}`}
                  className="w-full h-full border-0"
                  title={document.nom}
                />
              )}
              {previewType === 'none' && (
                <div className="flex flex-col items-center justify-center h-full gap-4 text-muted-foreground">
                  <FileWarning className="h-12 w-12 text-muted-foreground/50" />
                  <p className="text-sm">Aperçu non disponible pour ce type de fichier.</p>
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
