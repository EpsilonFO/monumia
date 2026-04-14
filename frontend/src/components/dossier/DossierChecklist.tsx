import { useRef, useState } from 'react';
import { CheckCircle2, Upload, Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { ChecklistItem, ChecklistItemStatus } from '@/types';

interface DossierChecklistProps {
  items: ChecklistItem[];
  onStatusChange: (itemId: string, status: ChecklistItemStatus) => void;
  onFileUpload?: (itemId: string, file: File, label: string) => Promise<void>;
  readOnly?: boolean;
}

export function DossierChecklist({ items, onStatusChange, onFileUpload, readOnly }: DossierChecklistProps) {
  const sorted = [...items].sort((a, b) => a.ordre - b.ordre);

  const uploaded = items.filter((i) => i.statut === 'fourni').length;

  return (
    <div className="space-y-3">
      {/* Summary */}
      <div className="flex items-center gap-2 text-sm text-[#8E92A4]">
        <span className="font-medium text-[#1B1E2E]">{uploaded}/{items.length}</span> documents ajoutés
      </div>

      {/* Document list */}
      <div className="space-y-1.5">
        {sorted.map((item) => (
          <DocumentRow
            key={item.id}
            item={item}
            readOnly={readOnly}
            onStatusChange={onStatusChange}
            onFileUpload={onFileUpload}
          />
        ))}
      </div>
    </div>
  );
}

function DocumentRow({
  item,
  readOnly,
  onStatusChange,
  onFileUpload,
}: {
  item: ChecklistItem;
  readOnly?: boolean;
  onStatusChange: (itemId: string, status: ChecklistItemStatus) => void;
  onFileUpload?: (itemId: string, file: File, label: string) => Promise<void>;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const isFourni = item.statut === 'fourni';

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (onFileUpload) {
      setUploading(true);
      try {
        await onFileUpload(item.id, file, item.label);
      } catch {
        // Upload failed — don't mark as fourni
      } finally {
        setUploading(false);
      }
    } else {
      // Fallback: just mark as fourni without uploading
      onStatusChange(item.id, 'fourni');
    }
    // Reset input so the same file can be re-selected
    e.target.value = '';
  };

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

      {!readOnly && (
        <>
          <input
            ref={inputRef}
            type="file"
            className="hidden"
            onChange={handleFileChange}
          />
          <button
            type="button"
            disabled={uploading}
            onClick={() => inputRef.current?.click()}
            className={cn(
              'inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors',
              uploading && 'opacity-60 cursor-not-allowed',
              isFourni
                ? 'border-green-300 text-green-700 hover:bg-green-100'
                : 'border-[#1A237E]/20 text-[#1A237E] hover:bg-[#E8EAF6]/50',
            )}
          >
            {uploading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Upload className="h-3 w-3" />}
            {uploading ? 'Envoi…' : isFourni ? 'Remplacer' : 'Ajouter'}
          </button>
        </>
      )}
    </div>
  );
}
