import { Link } from 'react-router';
import { ChevronRight } from 'lucide-react';
import { C } from '@/lib/brand';
import type { Monument, Notification } from '@/types';
import type { ProjectDeadline } from '@/lib/project-stats';
import { buildFeedRows, groupFeedByHorizon } from './echeances-alertes-utils';
import type { FeedRow } from './echeances-alertes-utils';
import { AllClear } from '@/components/illustrations';

const KIND_ACCENT: Record<FeedRow['kind'], { fg: string; tint: string }> = {
  urgent: { fg: C.danger, tint: C.paleDanger },
  warning: { fg: C.orange, tint: C.paleOrange },
  info: { fg: C.blue, tint: C.paleBlue },
};

interface AgendaPanelProps {
  deadlines: ProjectDeadline[];
  monuments: Monument[];
  notifications: Notification[];
  className?: string;
}

export function AgendaPanel({ deadlines, monuments, notifications, className }: AgendaPanelProps) {
  const groups = groupFeedByHorizon(buildFeedRows(deadlines, monuments, notifications));

  if (groups.length === 0) {
    return (
      <div
        className={`flex flex-col items-center gap-3 rounded-2xl border px-6 py-10 text-center ${className ?? ''}`}
        style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' }}
      >
        <AllClear />
        <p className="text-[15px] font-semibold" style={{ fontFamily: 'var(--font-serif)', color: C.ink }}>
          Votre agenda est dégagé
        </p>
        <p className="text-[12.5px]" style={{ color: C.grayMuted }}>
          Aucune échéance ni alerte. Tout est à jour.
        </p>
      </div>
    );
  }

  return (
    <div className={`space-y-5 ${className ?? ''}`}>
      {groups.map((group) => (
        <section key={group.key}>
          <h3 className="mb-2 px-1 text-[11.5px] font-semibold uppercase tracking-[0.14em]" style={{ color: C.grayMuted }}>
            {group.title}
            <span className="ml-2 font-normal" style={{ color: C.grayMuted, opacity: 0.7 }}>
              {group.rows.length}
            </span>
          </h3>
          <ul className="space-y-1.5">
            {group.rows.map((row) => {
              const accent = KIND_ACCENT[row.kind];
              const Icon = row.icon;
              const inner = (
                <div
                  className="group flex items-center gap-3 rounded-2xl border px-3.5 py-3 transition-colors hover:bg-[var(--color-secondary)]"
                  style={{ background: C.card, borderColor: C.border }}
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl" style={{ background: accent.tint, color: accent.fg }}>
                    <Icon className="h-4 w-4" aria-hidden />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13.5px] font-medium" style={{ color: C.ink }}>
                      {row.label}
                    </p>
                    <p className="truncate text-[11.5px]" style={{ color: C.grayMuted }}>
                      {row.sub}
                    </p>
                  </div>
                  <span
                    className="shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold tabular-nums"
                    style={{ background: accent.tint, color: accent.fg }}
                  >
                    {row.badge}
                  </span>
                  {row.to && (
                    <ChevronRight className="h-4 w-4 shrink-0 opacity-30 transition-transform group-hover:translate-x-0.5 group-hover:opacity-60" style={{ color: C.ink }} aria-hidden />
                  )}
                </div>
              );
              return <li key={row.id}>{row.to ? <Link to={row.to}>{inner}</Link> : inner}</li>;
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
