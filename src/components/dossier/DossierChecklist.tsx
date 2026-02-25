import { CheckCircle2, Clock, AlertCircle } from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { CHECKLIST_STATUS_CONFIG } from '@/constants/dossier-steps';
import type { ChecklistItem, ChecklistItemStatus } from '@/types';

interface DossierChecklistProps {
  items: ChecklistItem[];
  onStatusChange: (itemId: string, status: ChecklistItemStatus) => void;
  readOnly?: boolean;
}

const statusIcons = {
  fourni: CheckCircle2,
  en_attente: Clock,
  manquant: AlertCircle,
};

const categoryLabels: Record<string, string> = {
  administratif: 'Administratif',
  technique: 'Technique',
  financier: 'Financier',
  photographique: 'Photographique',
};

export function DossierChecklist({ items, onStatusChange, readOnly }: DossierChecklistProps) {
  const grouped = items.reduce<Record<string, ChecklistItem[]>>((acc, item) => {
    const cat = item.categorie;
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(item);
    return acc;
  }, {});

  const sortedCategories = Object.keys(grouped).sort((a, b) => {
    const minA = Math.min(...grouped[a].map((i) => i.ordre));
    const minB = Math.min(...grouped[b].map((i) => i.ordre));
    return minA - minB;
  });

  const stats = {
    fourni: items.filter((i) => i.statut === 'fourni').length,
    en_attente: items.filter((i) => i.statut === 'en_attente').length,
    manquant: items.filter((i) => i.statut === 'manquant').length,
    total: items.length,
  };

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="flex items-center gap-3 text-sm">
        <span className="text-green-600 font-medium">{stats.fourni} fournis</span>
        <span className="text-amber-600 font-medium">{stats.en_attente} en attente</span>
        <span className="text-red-600 font-medium">{stats.manquant} manquants</span>
        <span className="text-muted-foreground ml-auto">{stats.total} au total</span>
      </div>

      {/* Grouped checklist */}
      {sortedCategories.map((cat) => (
        <div key={cat} className="space-y-2">
          <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
            {categoryLabels[cat] ?? cat}
          </h4>
          <div className="space-y-1">
            {grouped[cat]
              .sort((a, b) => a.ordre - b.ordre)
              .map((item) => {
                const config = CHECKLIST_STATUS_CONFIG[item.statut];
                const Icon = statusIcons[item.statut];

                return (
                  <div
                    key={item.id}
                    className={cn(
                      'flex items-center gap-3 py-2 px-3 rounded-lg border',
                      config.bgColor
                    )}
                  >
                    <Icon className={cn('h-4 w-4 shrink-0', config.color)} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{item.label}</span>
                        {item.obligatoire && (
                          <Badge variant="outline" className="text-[10px] px-1 py-0 h-4">
                            Requis
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground truncate">
                        {item.description}
                      </p>
                    </div>
                    {!readOnly && (
                      <Select
                        value={item.statut}
                        onValueChange={(v) =>
                          onStatusChange(item.id, v as ChecklistItemStatus)
                        }
                      >
                        <SelectTrigger className="w-28 h-7 text-xs">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="fourni">Fourni</SelectItem>
                          <SelectItem value="en_attente">En attente</SelectItem>
                          <SelectItem value="manquant">Manquant</SelectItem>
                        </SelectContent>
                      </Select>
                    )}
                  </div>
                );
              })}
          </div>
        </div>
      ))}
    </div>
  );
}
