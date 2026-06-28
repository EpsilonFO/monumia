import { C } from '@/lib/brand';

export interface LegendItem {
  id: string;
  name: string;
  color: string;
  count: number;
}

interface Props {
  items: LegendItem[];
  activeId: string | null;
  onSelect: (id: string | null) => void;
}

export function ProjectLegend({ items, activeId, onSelect }: Props) {
  if (items.length === 0) return null;
  return (
    <div
      className="flex flex-wrap items-center gap-2 rounded-xl border px-3 py-2.5"
      style={{ background: C.card, borderColor: C.border }}
    >
      <span className="text-[11px] uppercase tracking-[0.08em] font-semibold text-muted-foreground">
        Projets
      </span>
      {items.map((it) => {
        const active = activeId === it.id;
        return (
          <button
            key={it.id}
            onClick={() => onSelect(active ? null : it.id)}
            className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] transition-all"
            style={{
              background: active ? `${it.color}1a` : 'transparent',
              border: `1px solid ${active ? it.color : C.border}`,
              color: C.ink,
            }}
          >
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: it.color }} />
            <span className="max-w-[180px] truncate">{it.name}</span>
            <span className="tabular-nums text-muted-foreground">{it.count}</span>
          </button>
        );
      })}
    </div>
  );
}
