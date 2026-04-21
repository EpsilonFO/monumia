import { CheckCircle2, Eye, Loader2, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { ChecklistItem } from '@/types';

interface DossierChecklistProps {
  items: ChecklistItem[];
  onRequestAttach?: (item: ChecklistItem) => void;
  onPreview?: (documentId: string) => void;
  onRequestDelete?: (item: ChecklistItem) => void;
  busyItemId?: string | null;
  readOnly?: boolean;
}

export function DossierChecklist({
  items,
  onRequestAttach,
  onPreview,
  onRequestDelete,
  busyItemId,
  readOnly,
}: DossierChecklistProps) {
  const sorted = [...items].sort((a, b) => a.ordre - b.ordre);
  const uploaded = items.filter((i) => i.statut === 'fourni').length;

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
            readOnly={readOnly}
            busy={busyItemId === item.id}
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
  readOnly,
  busy,
  onRequestAttach,
  onPreview,
  onRequestDelete,
}: {
  item: ChecklistItem;
  readOnly?: boolean;
  busy?: boolean;
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
        {isFourni && item.documentId && onPreview && (
          <button
            type="button"
            onClick={() => onPreview(item.documentId!)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-green-300 text-green-700 hover:bg-green-100 transition-colors"
          >
            <Eye className="h-3 w-3" />
            Voir
          </button>
        )}
        {!readOnly && isFourni && item.documentId && onRequestDelete && (
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
        {!readOnly && onRequestAttach && (
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
