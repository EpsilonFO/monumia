import { CheckCircle2, Download, Eye, Loader2, Lock, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import { templateService } from '@/services/template.service';
import { formatBadge } from '@/lib/template-format';
import type { ChecklistItem, Template } from '@/types';
import { useEffect, useState } from 'react';
import { useParams } from 'react-router';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { documentService } from '@/services/document.service';

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
      <div className="flex items-center gap-2 text-sm text-[#8E92A4]">
        <span className="font-medium text-[#1B1E2E]">{uploaded}/{items.length}</span> documents ajoutés
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
        isFourni ? 'bg-green-50/60 border-green-200' : 'border-[#E4E2DC] hover:border-[#C5C3BC]',
      )}
    >
      {isFourni ? (
        <CheckCircle2 className="h-4 w-4 shrink-0 text-green-600" />
      ) : (
        <div className="w-4 h-4 shrink-0 rounded-full border-2 border-[#E4E2DC]" />
      )}

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={cn('text-sm font-medium', isFourni && 'text-green-800')}>
            {item.label}
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
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-[#E4E2DC] text-[#8E92A4] cursor-default"
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
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-green-300 text-green-700 hover:bg-green-100 transition-colors"
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
              'inline-flex items-center justify-center h-[30px] w-[30px] rounded-lg border border-red-200 text-red-600 hover:bg-red-50 transition-colors',
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
                ? 'border-[#E4E2DC] text-[#5C6178] hover:bg-[#F8F7F4]'
                : 'border-[#1A237E]/20 text-[#1A237E] hover:bg-[#E8EAF6]/50',
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
    'inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border transition-colors border-[#f17105]/30 text-[#b9560a] bg-[#feeedd]/50 hover:bg-[#feeedd]';

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
        <p className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-[#8E92A4]">
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
                className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm transition-colors hover:bg-[#F8F7F4]"
              >
                <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold ${badge.className}`}>
                  {badge.label}
                </span>
                <span className="flex-1 truncate text-[13px] text-[#222b35]">{t.nom}</span>
                <Download className="h-3.5 w-3.5 shrink-0 text-[#8E92A4]" />
              </button>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}
