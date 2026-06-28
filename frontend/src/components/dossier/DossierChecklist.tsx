import { BookMarked, CheckCircle2, Download, Eye, Loader2, Lock, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { Link, useParams } from 'react-router';
import { ROUTES } from '@/constants/routes';
import { Badge } from '@/components/ui/badge';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';
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
  onRequestAttach?: (item: ChecklistItem) => void;
  onPreview?: (documentId: string) => void;
  onRequestDelete?: (item: ChecklistItem) => void;
  /** Vrai si l'utilisateur peut remplacer/supprimer la pièce (= il en est l'auteur). */
  canModifyItem?: (item: ChecklistItem) => boolean;
  busyItemId?: string | null;
  readOnly?: boolean;
}

export function DossierChecklist({
  items,
  templatesByItemId,
  onRequestAttach,
  onPreview,
  onRequestDelete,
  canModifyItem,
  busyItemId,
  readOnly,
}: DossierChecklistProps) {
  const sorted = [...items].sort((a, b) => a.ordre - b.ordre);
  const uploaded = items.filter((i) => i.statut === 'fourni').length;

  // Documents du projet que l'utilisateur a le DROIT de voir (le backend filtre
  // déjà selon la visibilité). Une pièce « fournie » dont le documentId n'y est
  // pas est donc masquée pour lui → cadenas au lieu de « Voir ». La page dossier
  // expose l'id projet via la route (/projets/:projetId/...), pas besoin d'y toucher.
  const { projetId } = useParams();
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
    documentService
      .getAll({ monumentId: projetId })
      .then((docs) => { if (!cancelled) setViewableDocIds(new Set(docs.map((d) => d.id))); })
      .catch(() => { if (!cancelled) setViewableDocIds(null); });
    return () => { cancelled = true; };
  }, [projetId, fourniKey]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm" style={{ color: 'var(--color-gray-muted)' }}>
          <span className="font-medium" style={{ color: 'var(--color-foreground)' }}>{uploaded}/{items.length}</span> documents ajoutés
        </p>
        <Link
          to={ROUTES.MODELES}
          className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors"
          style={{ color: 'var(--color-primary)' }}
        >
          <BookMarked className="h-3.5 w-3.5" />
          Bibliothèque de modèles
        </Link>
      </div>

      <div className="space-y-1.5">
        {sorted.map((item) => (
          <DocumentRow
            key={item.id}
            item={item}
            templates={templatesByItemId?.[item.id] ?? []}
            readOnly={readOnly}
            canModify={canModifyItem ? canModifyItem(item) : true}
            busy={busyItemId === item.id}
            hidden={
              !!item.documentId && viewableDocIds !== null && !viewableDocIds.has(item.documentId)
            }
            onRequestAttach={onRequestAttach}
            onPreview={onPreview}
            onRequestDelete={onRequestDelete}
          />
        ))}
      </div>
    </div>
  );
}

function DocumentRow({
  item,
  templates,
  readOnly,
  canModify = true,
  busy,
  hidden = false,
  onRequestAttach,
  onPreview,
  onRequestDelete,
}: {
  item: ChecklistItem;
  templates: Template[];
  readOnly?: boolean;
  canModify?: boolean;
  busy?: boolean;
  hidden?: boolean;
  onRequestAttach?: (item: ChecklistItem) => void;
  onPreview?: (documentId: string) => void;
  onRequestDelete?: (item: ChecklistItem) => void;
}) {
  const isFourni = item.statut === 'fourni';

  return (
    <div
      className={cn(
        'flex items-center gap-3 py-2.5 px-3 rounded-lg border transition-colors',
        isFourni ? 'bg-success-muted/60 border-success/30' : 'border-border hover:border-border/70',
      )}
    >
      {isFourni ? (
        <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
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
        </div>
        {item.description && (
          <p className="text-xs text-muted-foreground truncate">{item.description}</p>
        )}
      </div>

      <div className="flex items-center gap-1.5 shrink-0">
        <ModelButton templates={templates} />
        {isFourni && item.documentId && hidden && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <span
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-border text-muted-foreground cursor-default"
                  aria-label="Accès réservé"
                >
                  <Lock className="h-3 w-3" />
                  Réservé
                </span>
              </TooltipTrigger>
              <TooltipContent>Accès réservé&nbsp;: vous n'avez pas accès à ce document.</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
        {isFourni && item.documentId && !hidden && onPreview && (
          <button
            type="button"
            onClick={() => onPreview(item.documentId!)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-success/30 text-success hover:bg-success-muted transition-colors"
          >
            <Eye className="h-3 w-3" />
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
            <Trash2 className="h-3.5 w-3.5" />
          </button>
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
              <RefreshCw className="h-3 w-3" />
            ) : (
              <Plus className="h-3 w-3" />
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
        <Download className="h-3 w-3" />
        Modèle
      </button>
    );
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button type="button" className={pill}>
          <Download className="h-3 w-3" />
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
                <Download className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              </button>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}
