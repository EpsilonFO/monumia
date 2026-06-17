import { FolderKanban, ScrollText } from 'lucide-react';
import { C } from '@/lib/brand';
import type { DashboardStats } from '@/lib/project-stats';

interface KpiCardsProps {
  stats: DashboardStats;
}

interface Kpi {
  icon: typeof FolderKanban;
  label: string;
  hint: string;
  value: string;
  accent: string;
  tint: string;
}

export function KpiCards({ stats }: KpiCardsProps) {
  const cards: Kpi[] = [
    {
      icon: FolderKanban,
      label: 'Projets actifs',
      hint: 'Monuments suivis',
      value: String(stats.projetsActifs),
      accent: C.blue,
      tint: C.paleBlue,
    },
    {
      icon: ScrollText,
      label: 'Dossiers en cours',
      hint: 'Demandes en préparation',
      value: String(stats.dossiersEnCours),
      accent: C.orange,
      tint: C.paleOrange,
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {cards.map((c) => (
        <div
          key={c.label}
          className="flex items-center gap-5 rounded-2xl border px-6 py-5"
          style={{ background: C.card, borderColor: C.border }}
        >
          <div
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl"
            style={{ background: c.tint, color: c.accent }}
          >
            <c.icon className="h-5 w-5" aria-hidden />
          </div>
          <div className="min-w-0">
            <p
              className="text-[34px] font-bold leading-none tabular-nums"
              style={{ fontFamily: 'var(--font-serif)', color: c.accent }}
            >
              {c.value}
            </p>
            <p className="mt-1.5 text-[13px] font-semibold" style={{ color: C.ink }}>
              {c.label}
            </p>
            <p className="text-[11px]" style={{ color: C.ink, opacity: 0.5 }}>
              {c.hint}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
