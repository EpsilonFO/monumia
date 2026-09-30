import { useState, type ReactNode } from 'react';
import { Loader2, MoreVertical } from 'lucide-react';
import { toast } from 'sonner';
import {
  IconVoir, IconTelecharger, IconVerrou, type IconComponent,
} from '@/components/icons';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { C } from '@/lib/brand';
import { formatFileSize, formatShortDate } from '@/lib/format-utils';
import { getFileExtension } from '@/constants/file-types';
import { downloadDocument } from '@/lib/document-download';
import { typeIcon, typeLabel } from '@/lib/document-type-meta';
import { VISIBILITY_META } from '@/lib/document-visibility';
import { useDocumentThumbnail } from '@/components/document/useDocumentThumbnail';
import type { Document, DocumentType } from '@/types';

export interface DocMenuAction {
  label: string;
  icon: IconComponent;
  onClick: () => void;
  destructive?: boolean;
}

/**
 * Tonalité de l'aperçu — STRICTEMENT charte Monumia, sémantique :
 *   bleu = officiel/administratif · orange = argent · vert = pièce validée ·
 *   encre = divers. Pas de palette catégorielle hors-charte.
 */
const MONEY_TYPES = new Set<DocumentType>(['devis', 'facture']);
const VALID_TYPES = new Set<DocumentType>(['attestation', 'cerfa']);
const NEUTRAL_TYPES = new Set<DocumentType>(['rapport', 'correspondance', 'autre']);

interface Tone { band: string; soft: string; ink: string }
function toneFor(type: DocumentType): Tone {
  if (MONEY_TYPES.has(type)) return { band: C.orange, soft: C.paleOrange, ink: C.orange };
  if (VALID_TYPES.has(type)) return { band: 'var(--success)', soft: 'var(--success-muted)', ink: 'var(--success)' };
  if (NEUTRAL_TYPES.has(type)) return { band: C.ink, soft: 'var(--muted)', ink: 'var(--gray-fg)' };
  return { band: C.blue, soft: C.paleBlue, ink: C.blue };
}

interface DocumentCardViewProps {
  document: Document;
  onPreview: () => void;
  canDownload?: boolean;
  locations?: ReactNode;
  footer?: ReactNode;
  uploaderName?: string;
  menuActions: DocMenuAction[];
  variant?: 'normal' | 'trash';
}

export function DocumentCardView({
  document, onPreview, canDownload = true, locations, footer, uploaderName, menuActions, variant = 'normal',
}: DocumentCardViewProps) {
  const [downloading, setDownloading] = useState(false);
  const Icon = typeIcon(document.type);
  const tone = variant === 'trash'
    ? { band: C.ink, soft: 'var(--muted)', ink: 'var(--gray-fg)' }
    : toneFor(document.type);
  const restricted = document.visibility !== 'team';
  const { ref: thumbRef, preview } = useDocumentThumbnail(document.id, document.mimeType, document.nomFichier);
  const docDate = document.dateDocument ?? document.dateUpload;
  const ext = getFileExtension(document.nomFichier).toUpperCase();
  const provenance = locations ?? footer;
  const gridCols = preview?.kind === 'grid'
    ? Math.min(5, Math.max(1, ...preview.rows.map((r) => r.length)))
    : 1;

  const stop = (e: React.MouseEvent) => e.stopPropagation();

  const handleDownload = async (e: React.MouseEvent) => {
    stop(e);
    setDownloading(true);
    try {
      await downloadDocument(document);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Téléchargement impossible');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <article
      ref={thumbRef}
      onClick={onPreview}
      className="group relative flex flex-col gap-3 rounded-2xl border p-3.5 sm:flex-row sm:items-center sm:gap-5 sm:p-4 cursor-pointer transition-all duration-200 hover:-translate-y-0.5 hover:border-transparent hover:shadow-[var(--shadow-pop)]"
      style={{ background: C.card, borderColor: C.border, opacity: variant === 'trash' ? 0.85 : 1 }}
    >
      {/* Aperçu + infos */}
      <div className="flex items-center gap-4 min-w-0 flex-1">
        {/* Grand aperçu rectangulaire (168×112) : photo/PDF réel, sinon aplat couleur */}
        <div
          className="relative shrink-0 overflow-hidden rounded-2xl flex flex-col items-center justify-center gap-1 w-[127.5px] h-[86.5px] sm:w-[191px] sm:h-[127.5px]"
          style={{ background: preview?.kind === 'image' ? C.blueDark : (preview?.kind === 'text' || preview?.kind === 'grid') ? '#fff' : tone.band }}
        >
          {preview?.kind === 'image' ? (
            <img
              src={preview.url}
              alt=""
              className={`absolute inset-0 h-full w-full object-cover ${preview.fit === 'top' ? 'object-top' : ''}`}
            />
          ) : preview?.kind === 'text' ? (
            <>
              <span className="absolute inset-x-0 top-0 h-1.5" style={{ background: tone.band }} />
              <p
                className="absolute inset-0 mt-1.5 px-2.5 py-2 sm:px-3 sm:py-2.5 text-[12px] sm:text-[12px] leading-[1.5] whitespace-pre-wrap break-words overflow-hidden text-left"
                style={{ color: '#3a3f47' }}
              >
                {preview.text}
              </p>
              <span className="pointer-events-none absolute inset-x-0 bottom-0 h-8" style={{ background: 'linear-gradient(transparent, #fff)' }} />
            </>
          ) : preview?.kind === 'grid' ? (
            <>
              <span className="absolute inset-x-0 top-0 h-1.5" style={{ background: tone.band }} />
              <div className="absolute inset-0 mt-1.5 p-1.5 overflow-hidden">
                <div
                  className="grid w-full"
                  style={{ gridTemplateColumns: `repeat(${gridCols}, minmax(0, 1fr))`, gap: '1px', background: '#e6e6e6', border: '1px solid #e6e6e6' }}
                >
                  {preview.rows.flatMap((row, r) =>
                    Array.from({ length: gridCols }).map((_, c) => (
                      <div
                        key={`${r}-${c}`}
                        className="truncate bg-white px-1 py-[2px] text-[12px] sm:text-[12px] leading-tight text-left"
                        style={{ color: '#3a3f47', fontWeight: r === 0 ? 600 : 400 }}
                      >
                        {row[c] ?? ''}
                      </div>
                    )),
                  )}
                </div>
              </div>
              <span className="pointer-events-none absolute inset-x-0 bottom-0 h-8" style={{ background: 'linear-gradient(transparent, #fff)' }} />
            </>
          ) : (
            <>
              <Icon className="h-8 w-8 sm:h-10 sm:w-10 text-white" weight="bold" />
              <span
                className="text-[13px] sm:text-[14px] font-bold uppercase tracking-wide text-white"
                style={{ fontFamily: "'PT Serif', Georgia, serif" }}
              >
                {typeLabel(document.type)}
              </span>
              <Icon
                className="pointer-events-none absolute -right-3 -bottom-4 h-24 w-24 text-white"
                weight="fill"
                style={{ opacity: 0.13 }}
              />
            </>
          )}
        </div>

        {/* Titre + repères */}
        <div className="min-w-0 flex-1 flex flex-col gap-1.5">
          <h3
            className="text-[18px] sm:text-[19px] font-semibold leading-snug line-clamp-2"
            style={{ fontFamily: "'PT Serif', Georgia, serif", color: C.ink }}
            title={document.nom}
          >
            {document.nom}
          </h3>

          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[14.5px] text-muted-foreground">
            {preview && (
              <span
                className="inline-flex items-center rounded-md px-2 py-0.5 text-[13px] font-semibold"
                style={{ background: tone.soft, color: tone.ink }}
              >
                {typeLabel(document.type)}
              </span>
            )}
            {ext && <span className="font-medium">{ext}</span>}
            <span aria-hidden>·</span>
            <span>{formatFileSize(document.tailleFichier)}</span>
            {docDate && (<><span aria-hidden>·</span><span>{formatShortDate(docDate)}</span></>)}
            {restricted && (
              <span
                className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[13px] font-semibold"
                style={{ background: C.paleBlue, color: C.blue }}
                title={VISIBILITY_META[document.visibility].help}
              >
                <IconVerrou className="h-3 w-3" weight="bold" />Accès restreint
              </span>
            )}
            {uploaderName && <span>· {uploaderName}</span>}
          </div>

          {provenance && (
            <div className="flex items-center gap-1.5 text-[14.5px] text-muted-foreground">
              {provenance}
            </div>
          )}
        </div>
      </div>

      {/* Actions — toujours visibles */}
      <div className="flex items-center gap-2 sm:shrink-0" onClick={stop}>
        <button
          onClick={(e) => { stop(e); onPreview(); }}
          className="inline-flex flex-1 sm:flex-none items-center justify-center gap-1.5 h-10 px-4 rounded-xl text-[15px] font-semibold text-white transition-all hover:brightness-110"
          style={{ background: C.blue }}
          title="Voir le document"
        >
          <IconVoir className="h-4 w-4" weight="bold" />Voir
        </button>
        {canDownload && (
          <button
            onClick={handleDownload}
            disabled={downloading}
            className="inline-flex flex-1 sm:flex-none items-center justify-center gap-1.5 h-10 px-4 rounded-xl text-[15px] font-semibold transition-colors disabled:opacity-60 hover:bg-black/[0.04]"
            style={{ background: 'transparent', color: C.ink, border: `1px solid ${C.border}` }}
            title="Télécharger"
          >
            {downloading
              ? <Loader2 className="h-4 w-4 animate-spin" />
              : <IconTelecharger className="h-4 w-4" weight="bold" />}
            Télécharger
          </button>
        )}
        {menuActions.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={stop}>
              <button
                className="shrink-0 h-10 w-10 flex items-center justify-center rounded-xl transition-colors hover:bg-black/[0.04]"
                style={{ border: `1px solid ${C.border}`, color: C.grayFg }}
                title="Plus d'actions"
                aria-label="Plus d'actions"
              >
                <MoreVertical className="h-4 w-4" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" onClick={stop}>
              {menuActions.map((a) => (
                <DropdownMenuItem
                  key={a.label}
                  className={a.destructive ? 'text-destructive' : undefined}
                  onClick={a.onClick}
                >
                  <a.icon className="h-3.5 w-3.5 mr-2" />{a.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
    </article>
  );
}
