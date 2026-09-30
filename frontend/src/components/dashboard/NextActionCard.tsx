import { useState } from 'react';
import { Link } from 'react-router';
import { ArrowRight, ChevronRight } from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { fr } from 'date-fns/locale';
import { C, DEADLINE_TONE } from '@/lib/brand';
import { deadlineLabel } from '@/lib/date-utils';
import { deadlineLink } from '@/lib/project-stats';
import type { ProjectDeadline } from '@/lib/project-stats';
import type { FeedRow } from './echeances-alertes-utils';
import { AllClear } from '@/components/illustrations';

const KIND_ACCENT: Record<FeedRow['kind'], { fg: string; tint: string }> = {
  urgent: { fg: C.danger, tint: C.paleDanger },
  warning: { fg: C.orange, tint: C.paleOrange },
  info: { fg: C.blue, tint: C.paleBlue },
};

/** Nombre de lignes « Ensuite » visibles avant dépliage. */
const UPCOMING_PREVIEW = 3;

interface NextActionCardProps {
  /** Échéance(s) les plus proches — affichées dans le bloc principal. */
  deadlines: ProjectDeadline[];
  /** Reste du flux agenda (échéances suivantes, notifications). */
  upcoming: FeedRow[];
}

/**
 * Carte agenda unifiée : l'action prioritaire en avant, suivie des prochaines
 * échéances et alertes (« Ensuite »). Remplace l'ancien duo NextActionCard +
 * AgendaPanel qui répétait la même information en haut et en bas de page.
 */
export function NextActionCard({ deadlines, upcoming }: NextActionCardProps) {
  if (deadlines.length === 0 && upcoming.length === 0) {
    return (
      <div
        className="flex items-center gap-4 rounded-2xl border px-6 py-5"
        style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' }}
      >
        <AllClear />
        <div>
          <p className="text-[17px] font-semibold" style={{ fontFamily: 'var(--font-serif)', color: C.ink }}>
            Tout est à jour
          </p>
          <p className="text-[15px]" style={{ color: C.grayMuted }}>
            Aucune échéance ne réclame votre attention pour le moment.
          </p>
        </div>
      </div>
    );
  }

  const first = deadlines[0];

  return (
    <div
      className="overflow-hidden rounded-2xl border"
      style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' }}
    >
      {first ? <MainAction deadlines={deadlines} /> : null}
      {upcoming.length > 0 && (
        <UpcomingList rows={upcoming} standalone={!first} />
      )}
    </div>
  );
}

/** Bloc principal : la prochaine action, avec date façon éphéméride et CTA. */
function MainAction({ deadlines }: { deadlines: ProjectDeadline[] }) {
  const [first, ...rest] = deadlines;
  const { text, urgency } = deadlineLabel(first.date);
  const tone = DEADLINE_TONE[urgency];
  const date = parseISO(first.date);
  const month = format(date, 'MMM', { locale: fr }).replace('.', '');

  return (
    <Link
      to={deadlineLink(first)}
      className="group flex flex-col gap-4 px-6 py-5 transition-colors hover:bg-muted/50 sm:flex-row sm:items-center"
    >
      <span
        className="flex h-16 w-14 shrink-0 flex-col items-center justify-center rounded-2xl"
        style={{ background: tone.tint, color: tone.fg }}
        aria-hidden
      >
        <span className="text-[25px] font-bold leading-none tabular-nums" style={{ fontFamily: 'var(--font-serif)' }}>
          {format(date, 'd')}
        </span>
        <span className="mt-1 text-[12px] font-semibold uppercase tracking-[0.12em]">{month}</span>
      </span>
      <div className="min-w-0 flex-1">
        <p className="inline-flex items-center gap-2 text-[12px] font-semibold uppercase tracking-[0.18em]" style={{ color: tone.fg }}>
          <span aria-hidden style={{ width: 20.5, height: 2, borderRadius: 2, background: tone.node }} />
          À faire maintenant · {text}
        </p>
        <p className="mt-1 truncate text-[19px] font-semibold" style={{ fontFamily: 'var(--font-serif)', color: C.ink }}>
          {first.label}
        </p>
        <p className="text-[14.5px]" style={{ color: C.grayMuted }}>
          {first.source === 'aide' ? 'Demande d’aide' : 'Dossier'}
          {rest.length > 0 ? ` · et ${rest.length} autre${rest.length > 1 ? 's' : ''} ce jour-là` : ''}
        </p>
      </div>
      <span
        className="inline-flex shrink-0 items-center gap-1.5 self-start rounded-xl px-4 py-2.5 text-[15px] font-semibold text-white sm:self-center"
        style={{ background: C.orange }}
      >
        Je m'en occupe
        <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-0.5" />
      </span>
    </Link>
  );
}

/** Section « Ensuite » : les prochaines échéances/alertes en lignes compactes, dépliables. */
function UpcomingList({ rows, standalone }: { rows: FeedRow[]; standalone: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? rows : rows.slice(0, UPCOMING_PREVIEW);
  const hidden = rows.length - UPCOMING_PREVIEW;

  return (
    <div
      className="px-6 pb-4 pt-4"
      style={standalone ? undefined : { borderTop: `1px dashed ${C.border}` }}
    >
      <h3 className="mb-2 text-[12px] font-semibold uppercase tracking-[0.18em]" style={{ color: C.grayMuted }}>
        {standalone ? 'À noter' : 'Ensuite'}
      </h3>
      <ul>
        {visible.map((row) => {
          const accent = KIND_ACCENT[row.kind];
          const inner = (
            <div className="group flex items-center gap-3 rounded-xl px-2 py-2 transition-colors hover:bg-muted/60">
              <span
                className="inline-flex min-w-16 shrink-0 justify-center whitespace-nowrap rounded-full px-2 py-0.5 text-[13px] font-semibold tabular-nums"
                style={{ background: accent.tint, color: accent.fg }}
              >
                {row.badge}
              </span>
              <p className="min-w-0 flex-1 truncate text-[15px] font-medium" style={{ color: C.ink }}>
                {row.label}
              </p>
              <span className="hidden shrink-0 text-[13.5px] sm:inline" style={{ color: C.grayMuted }}>
                {row.sub}
              </span>
              {row.to && (
                <ChevronRight
                  className="h-4 w-4 shrink-0 opacity-30 transition-transform group-hover:translate-x-0.5 group-hover:opacity-60"
                  style={{ color: C.ink }}
                  aria-hidden
                />
              )}
            </div>
          );
          return <li key={row.id}>{row.to ? <Link to={row.to}>{inner}</Link> : inner}</li>;
        })}
      </ul>
      {hidden > 0 && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="mt-1 px-2 text-[14px] font-semibold transition-opacity hover:opacity-70"
          style={{ color: C.blue }}
        >
          {expanded ? 'Réduire' : `+ ${hidden} autre${hidden > 1 ? 's' : ''}`}
        </button>
      )}
    </div>
  );
}
