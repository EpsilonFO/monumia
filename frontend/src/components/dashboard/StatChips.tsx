import { IconMonument, IconDossier, IconAide } from '@/components/icons';
import { C } from '@/lib/brand';
import { formatCurrency } from '@/lib/format-utils';
import type { ComponentType } from 'react';
import type { DashboardStats } from '@/lib/project-stats';
import { Euro } from 'lucide-react';

interface Chip {
  icon: ComponentType<{ size?: number; className?: string }>;
  value: string;
  label: string;
  accent: string;
  tint: string;
}

export function StatChips({ stats }: { stats: DashboardStats }) {
  const chips: Chip[] = [
    { icon: IconMonument, value: String(stats.projetsActifs), label: 'Projets suivis', accent: C.blue, tint: C.paleBlue },
    { icon: IconDossier, value: String(stats.dossiersEnCours), label: 'Dossiers en cours', accent: C.orange, tint: C.paleOrange },
    { icon: IconAide, value: String(stats.aidesIdentifiees), label: 'Aides identifiées', accent: C.blueLight, tint: C.paleBlue },
    { icon: Euro, value: formatCurrency(stats.montantPotentielTotal), label: 'Montant potentiel', accent: C.blueDark, tint: C.paleBlue },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {chips.map((c) => {
        const Icon = c.icon;
        return (
          <div
            key={c.label}
            className="flex items-center gap-3 rounded-2xl border px-4 py-3.5"
            style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' }}
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" style={{ background: c.tint, color: c.accent }}>
              <Icon size={20} />
            </span>
            <div className="min-w-0">
              <p className="truncate text-[22px] font-bold leading-none tabular-nums" style={{ fontFamily: 'var(--font-serif)', color: c.accent }}>
                {c.value}
              </p>
              <p className="mt-1 truncate text-[12px] font-medium" style={{ color: C.grayMuted }}>
                {c.label}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
