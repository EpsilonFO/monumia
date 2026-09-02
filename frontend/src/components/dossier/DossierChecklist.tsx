import { Loader2 } from 'lucide-react';
import {
  IconSucces, IconTelecharger, IconVoir, IconVerrou, IconAjouter, IconRafraichir, IconSupprimer, IconLienExterne, IconAttention,
} from '@/components/icons';
import { useParams } from 'react-router';
import { toast } from 'sonner';
import { Badge } from '@/components/ui/badge';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import { dossierService } from '@/services/dossier.service';
import { templateService } from '@/services/template.service';
import { formatBadge } from '@/lib/template-format';
import type { ChecklistItem, Template } from '@/types';
import { useEffect, useState } from 'react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { documentService } from '@/services/document.service';
import { compterChecklist } from '@/lib/checklist-progress';

/** Défense : un label malformé (dossier stocké avec un objet document
 *  {nom, …} au lieu d'une chaîne) ne doit pas faire planter le rendu React. */
function labelText(label: unknown): string {
  if (typeof label === 'string') return label;
  if (label && typeof label === 'object' && 'nom' in label) {
    return String((label as { nom: unknown }).nom ?? '');
  }
  return '';
}

interface DossierChecklistProps {
  items: ChecklistItem[];
  /** Modèles de la bibliothèque correspondant à chaque pièce (par id de pièce). */
  templatesByItemId?: Record<string, Template[]>;
  /** Lien de téléchargement officiel de la pièce (Cerfa / formulaire), par id de pièce. */
  documentUrlByItemId?: Record<string, string>;
  onRequestAttach?: (item: ChecklistItem) => void;
  onPreview?: (documentId: string) => void;
  onRequestDelete?: (item: ChecklistItem) => void;
  /** Confirme une pièce reprise (« c'est bien ce document »). */
  onConfirm?: (item: ChecklistItem) => void;
  /** Rejette une pièce reprise (mauvais document). */
  onReject?: (item: ChecklistItem) => void;
  /** Vrai si l'utilisateur peut remplacer/supprimer la pièce (= il en est l'auteur). */
  canModifyItem?: (item: ChecklistItem) => boolean;
  /** Nom du fichier zip proposé au téléchargement de l'ensemble des pièces. */
  archiveName?: string;
  busyItemId?: string | null;
  readOnly?: boolean;
}

export function DossierChecklist({
  items,
  templatesByItemId,
  documentUrlByItemId,
  onRequestAttach,
  onPreview,
  onRequestDelete,
  onConfirm,
  onReject,
  canModifyItem,
  archiveName,
  busyItemId,
  readOnly,
}: DossierChecklistProps) {
  const sorted = [...items].sort((a, b) => a.ordre - b.ordre);
  const { confirmees, aVerifier, total } = compterChecklist(items);

  // Documents que l'utilisateur a le DROIT de voir (le backend filtre déjà selon
  // la visibilité). Une pièce dont le documentId n'y est pas est masquée pour lui
  // → cadenas au lieu de « Voir ». La page dossier expose l'id projet via la
  // route (/projets/:projetId/...), pas besoin d'y toucher.
  const { projetId, dossierId } = useParams();
  const [viewableDocIds, setViewableDocIds] = useState<Set<string> | null>(null);

  // Re-fetch quand l'ensemble des pièces fournies change (dépôt/remplacement) :
  // sans ça, un document fraîchement déposé n'est pas dans l'ensemble « visibles »
  // et s'affiche à tort comme « Réservé » jusqu'au rechargement de la page.
  const fourniKey = items
    .filter((i) => i.documentId)
    .map((i) => i.documentId)
    .sort()
    .join(',');

  useEffect(() => {
    if (!projetId) { setViewableDocIds(null); return; }
    let cancelled = false;
    (async () => {
      let visibles: Set<string>;
      try {
        const docs = await documentService.getAll({ monumentId: projetId });
        visibles = new Set(docs.map((d) => d.id));
      } catch {
        if (!cancelled) setViewableDocIds(null);
        return;
      }
      // Une pièce reprise vient par construction d'un AUTRE projet (ou d'aucun) :
      // son document n'est jamais dans la liste du projet, et conclure « accès
      // réservé » afficherait un cadenas sur mon propre RIB. On interroge donc le
      // backend document par document — `getById` applique la même règle de
      // visibilité (`_require_document_view`), aucun chemin d'accès parallèle.
      const absents = [...new Set(fourniKey ? fourniKey.split(',') : [])]
        .filter((id) => id && !visibles.has(id));
      const resolus = await Promise.all(
        absents.map((id) => documentService.getById(id).then(() => id).catch(() => null)),
      );
      if (cancelled) return;
      for (const id of resolus) if (id) visibles.add(id);
      setViewableDocIds(visibles);
    })();
    return () => { cancelled = true; };
  }, [projetId, fourniKey]);

  // Téléchargement de l'ensemble des pièces en un zip. Le backend n'y met que
  // les documents que l'appelant a le droit de consulter : une pièce « Réservé »
  // est absente de l'archive, sans erreur.
  const [downloading, setDownloading] = useState(false);
  const hasUploaded = items.some((i) => i.documentId);

  const handleDownloadAll = async () => {
    if (!dossierId) return;
    setDownloading(true);
    try {
      await dossierService.downloadArchive(dossierId, archiveName ?? 'dossier');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Téléchargement impossible');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm" style={{ color: 'var(--color-gray-muted)' }}>
          <span className="font-medium" style={{ color: 'var(--color-foreground)' }}>{confirmees}/{total}</span> documents confirmés
          {aVerifier > 0 && <span> · {aVerifier} à vérifier</span>}
        </p>
        {hasUploaded && dossierId && (
          <button
            type="button"
            onClick={handleDownloadAll}
            disabled={downloading}
            className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-secondary/50 disabled:opacity-60 disabled:cursor-not-allowed"
            style={{ color: 'var(--color-primary)' }}
            title="Télécharger toutes les pièces téléversées dans une archive zip"
          >
            {downloading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <IconTelecharger className="h-3.5 w-3.5" />
            )}
            {downloading ? 'Préparation…' : 'Télécharger le dossier'}
          </button>
        )}
      </div>

      <div className="space-y-1.5">
        {sorted.map((item) => (
          <DocumentRow
            key={item.id}
            item={item}
            templates={templatesByItemId?.[item.id] ?? []}
            documentUrl={documentUrlByItemId?.[item.id]}
            readOnly={readOnly}
            canModify={canModifyItem ? canModifyItem(item) : true}
            busy={busyItemId === item.id}
            hidden={
              !!item.documentId && viewableDocIds !== null && !viewableDocIds.has(item.documentId)
            }
            onRequestAttach={onRequestAttach}
            onPreview={onPreview}
            onRequestDelete={onRequestDelete}
            onConfirm={onConfirm}
            onReject={onReject}
          />
        ))}
      </div>
    </div>
  );
}

function DocumentRow({
  item,
  templates,
  documentUrl,
  readOnly,
  canModify = true,
  busy,
  hidden = false,
  onRequestAttach,
  onPreview,
  onRequestDelete,
  onConfirm,
  onReject,
}: {
  item: ChecklistItem;
  templates: Template[];
  documentUrl?: string;
  readOnly?: boolean;
  canModify?: boolean;
  busy?: boolean;
  hidden?: boolean;
  onRequestAttach?: (item: ChecklistItem) => void;
  onPreview?: (documentId: string) => void;
  onRequestDelete?: (item: ChecklistItem) => void;
  onConfirm?: (item: ChecklistItem) => void;
  onReject?: (item: ChecklistItem) => void;
}) {
  const isFourni = item.statut === 'fourni';
  const isRepris = item.statut === 'repris';

  return (
    <div
      className={cn(
        'flex items-center gap-3 py-2.5 px-3 rounded-lg border transition-colors',
        isFourni && 'bg-success-muted/60 border-success/30',
        isRepris && !item.perime && 'bg-secondary/40 border-primary/30',
        isRepris && item.perime && 'bg-warning-muted/50 border-accent/40',
        !isFourni && !isRepris && 'border-border hover:border-border/70',
      )}
    >
      {isFourni ? (
        <IconSucces className="h-4 w-4 shrink-0 text-success" />
      ) : isRepris ? (
        <IconRafraichir className="h-4 w-4 shrink-0" style={{ color: 'var(--color-primary)' }} />
      ) : (
        <div className="w-4 h-4 shrink-0 rounded-full border-2 border-border" />
      )}

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={cn('text-sm font-medium', isFourni && 'text-success')}>
            {labelText(item.label)}
          </span>
          {item.obligatoire && (
            <Badge variant="outline" className="text-[10px] px-1 py-0 h-4">
              Requis
            </Badge>
          )}
          {isRepris && !item.perime && (
            <Badge variant="outline" className="text-[10px] px-1 py-0 h-4 border-primary/40 text-primary">
              Repris — à vérifier
            </Badge>
          )}
          {isRepris && item.perime && (
            <Badge variant="outline" className="text-[10px] px-1 py-0 h-4 border-accent/50 text-warning">
              <IconAttention className="h-2.5 w-2.5 mr-0.5" />
              Repris — document ancien
            </Badge>
          )}
        </div>
        {item.description && (
          <p className="text-xs text-muted-foreground truncate">{item.description}</p>
        )}
      </div>

      <div className="flex items-center gap-1.5 shrink-0">
        {/* Confirmer une pièce qu'on ne peut pas ouvrir serait confirmer à
            l'aveugle : le bouton disparaît avec « Voir », il ne reste que le
            cadenas. Le rejet, lui, ne demande pas de consulter le document — il
            reste offert pour ne pas laisser la pièce dans une impasse. */}
        {!readOnly && isRepris && !hidden && onConfirm && (
          <button
            type="button"
            disabled={busy}
            onClick={() => onConfirm(item)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-success/30 text-success hover:bg-success-muted transition-colors"
          >
            <IconSucces className="h-3 w-3" />
            C’est bien ça
          </button>
        )}
        {!readOnly && isRepris && onReject && (
          <button
            type="button"
            disabled={busy}
            onClick={() => onReject(item)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-border text-muted-foreground hover:bg-muted transition-colors"
          >
            Ce n’est pas ça
          </button>
        )}
        <ModelButton templates={templates} />
        {(isFourni || isRepris) && item.documentId && hidden && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <span
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-border text-muted-foreground cursor-default"
                  aria-label="Accès réservé"
                >
                  <IconVerrou className="h-3 w-3" />
                  Réservé
                </span>
              </TooltipTrigger>
              <TooltipContent>Accès réservé&nbsp;: vous n'avez pas accès à ce document.</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
        {(isFourni || isRepris) && item.documentId && !hidden && onPreview && (
          <button
            type="button"
            onClick={() => onPreview(item.documentId!)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-success/30 text-success hover:bg-success-muted transition-colors"
          >
            <IconVoir className="h-3 w-3" />
            Voir
          </button>
        )}
        {!readOnly && isFourni && item.documentId && onRequestDelete && canModify && !hidden && (
          <button
            type="button"
            disabled={busy}
            onClick={() => onRequestDelete(item)}
            aria-label="Supprimer"
            className={cn(
              'inline-flex items-center justify-center h-[30px] w-[30px] rounded-lg border border-destructive/20 text-destructive hover:bg-destructive-muted transition-colors',
              busy && 'opacity-60 cursor-not-allowed',
            )}
          >
            <IconSupprimer className="h-3.5 w-3.5" />
          </button>
        )}
        {documentUrl && (
          <a
            href={documentUrl}
            target="_blank"
            rel="noopener noreferrer"
            title="Télécharger le document (formulaire / Cerfa / modèle officiel)"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-primary/20 text-primary hover:bg-secondary/50 transition-colors"
          >
            <IconTelecharger className="h-3 w-3" />
            Télécharger
            <IconLienExterne className="h-3 w-3" />
          </a>
        )}
        {!readOnly && onRequestAttach && (!isFourni || canModify) && !hidden && (
          <button
            type="button"
            disabled={busy}
            onClick={() => onRequestAttach(item)}
            className={cn(
              'inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors',
              busy && 'opacity-60 cursor-not-allowed',
              isFourni
                ? 'border-border text-muted-foreground hover:bg-muted'
                : 'border-primary/20 text-primary hover:bg-secondary/50',
            )}
          >
            {busy ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : isFourni ? (
              <IconRafraichir className="h-3 w-3" />
            ) : (
              <IconAjouter className="h-3 w-3" />
            )}
            {busy ? 'Envoi…' : isFourni ? 'Remplacer' : 'Ajouter'}
          </button>
        )}
      </div>
    </div>
  );
}

// Pastille « Modèle » : présente quand au moins un modèle de la bibliothèque
// correspond à la pièce. Un seul modèle → téléchargement direct ; plusieurs →
// liste dans un popover. Aucun modèle → rien (cas fréquent, assumé).
function ModelButton({ templates }: { templates: Template[] }) {
  if (templates.length === 0) return null;

  const pill =
    'inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border transition-colors border-accent/30 text-warning bg-warning-muted/50 hover:bg-warning-muted';

  if (templates.length === 1) {
    const t = templates[0];
    return (
      <button
        type="button"
        onClick={() => templateService.download(t)}
        className={pill}
        title={`Télécharger le modèle : ${t.nom}`}
      >
        <IconTelecharger className="h-3 w-3" />
        Modèle
      </button>
    );
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button type="button" className={pill}>
          <IconTelecharger className="h-3 w-3" />
          Modèles ({templates.length})
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 p-1.5">
        <p className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          Modèles suggérés
        </p>
        <div className="space-y-0.5">
          {templates.map((t) => {
            const badge = formatBadge(t.extension);
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => templateService.download(t)}
                className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm transition-colors hover:bg-muted"
              >
                <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold ${badge.className}`}>
                  {badge.label}
                </span>
                <span className="flex-1 truncate text-[13px] text-foreground">{t.nom}</span>
                <IconTelecharger className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              </button>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}
