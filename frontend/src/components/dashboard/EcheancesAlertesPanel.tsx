import { Link } from 'react-router';
import { ChevronRight, CalendarClock } from 'lucide-react';
import { C } from '@/lib/brand';
import type { Monument, Notification } from '@/types';
import type { ProjectDeadline } from '@/lib/project-stats';
import { buildFeedRows } from './echeances-alertes-utils';
import type { FeedKind, FeedRow } from './echeances-alertes-utils';

interface EcheancesAlertesPanelProps {
  deadlines: ProjectDeadline[];
  monuments: Monument[];
  notifications: Notification[];
  className?: string;
}

interface KindStyle {
  node: string; // couleur du nœud (remplissage si `filled`, sinon contour)
  ring: string; // couleur du halo (rgba)
  tint: string; // fond au survol + fond du badge
  fg: string; // texte du badge
  filled: boolean; // nœud plein (urgent) ou anneau (le reste)
  pulse: boolean; // halo pulsant (urgent uniquement)
  size: number; // diamètre du nœud, px
}

// Code couleur unique des échéances (voir DEADLINE_TONE) :
//   urgent < 30 j → rouge · warning 30–100 j → orange · info > 100 j → bleu
const KIND: Record<FeedKind, KindStyle> = {
  urgent: { node: C.danger, ring: 'rgba(192,39,29,0.5)', tint: C.paleDanger, fg: C.danger, filled: true, pulse: true, size: 13 },
  warning: { node: C.orange, ring: 'rgba(241,113,5,0.45)', tint: C.paleOrange, fg: C.orange, filled: false, pulse: false, size: 11 },
  info: { node: C.blueLight, ring: 'rgba(92,149,255,0.5)', tint: C.paleBlue, fg: C.blue, filled: false, pulse: false, size: 10 },
};


/**
 * Carte unifiée du tableau de bord — fusionne l'ancien « Échéancier global » et
 * l'ancienne carte « Alertes ». Un flux chronologique unique (échéances, péril,
 * dossiers incomplets, notifications) trié par urgence puis par date, rendu sous
 * forme de frise verticale.
 */
export function EcheancesAlertesPanel({
  deadlines,
  monuments,
  notifications,
  className,
}: EcheancesAlertesPanelProps) {
  // On affiche toutes les lignes, sans plafond : l'échéancier reprend l'intégralité
  // des échéances à venir (même lointaines), plus les alertes (péril, notifications).
  const items = buildFeedRows(deadlines, monuments, notifications);

  return (
    <div
      className={`overflow-hidden rounded-xl border ${className ?? ''}`}
      style={{ background: C.card, borderColor: C.border }}
    >
      {/* Légende du code couleur des échéances + compteur */}
      <div
        className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b px-4 py-2.5"
        style={{ borderColor: C.border }}
      >
        <LegendDot color={C.danger} label="moins de 30 j" />
        <LegendDot color={C.orange} label="30 à 100 j" />
        <LegendDot color={C.blueLight} label="plus de 100 j" />
        {items.length > 0 && (
          <span
            className="ml-auto inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[11px] font-bold text-white"
            style={{ background: C.blue }}
          >
            {items.length}
          </span>
        )}
      </div>

      {items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
          <span
            className="flex h-11 w-11 items-center justify-center rounded-full"
            style={{ background: C.paleBlue }}
          >
            <CalendarClock className="h-5 w-5" style={{ color: C.blue }} aria-hidden />
          </span>
          <p className="text-[13px]" style={{ fontFamily: 'var(--font-serif)', color: C.ink }}>
            Aucune échéance ni alerte
          </p>
          <p className="text-[11px]" style={{ color: C.ink, opacity: 0.5 }}>
            Tout est à jour.
          </p>
        </div>
      ) : (
        <div className="px-3 py-3">
          {/* Frise verticale : une spine dégradée + un nœud par ligne */}
          <ol className="flex flex-col" aria-label="Échéances et alertes">
            {items.map((r, i) => (
              <FeedItem key={r.id} row={r} next={items[i + 1]} index={i} />
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

/** Pastille de légende : un point coloré + son intitulé. */
function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px]" style={{ color: C.ink, opacity: 0.7 }}>
      <span className="inline-block h-2 w-2 rounded-full" style={{ background: color }} aria-hidden />
      {label}
    </span>
  );
}

function FeedItem({ row, next, index }: { row: FeedRow; next?: FeedRow; index: number }) {
  const u = KIND[row.kind];
  const nextColor = next ? KIND[next.kind].node : u.node;
  const Icon = row.icon;

  const inner = (
    <span className="group relative flex items-stretch gap-3 py-1.5 pl-1 pr-1" style={{ ['--tint' as string]: u.tint }}>
      {/* Rail : spine (connecteur) + halo + nœud — jamais recouvert par le survol */}
      <span className="relative w-4 shrink-0" aria-hidden>
        {next && (
          <span
            className="frise-draw absolute w-0.5"
            style={{
              left: 'calc(50% - 1px)',
              top: '50%',
              height: 'calc(100% + 20px)',
              background: `linear-gradient(to bottom, ${u.node}, ${nextColor})`,
              animationDelay: `${index * 80 + 40}ms`,
            }}
          />
        )}

        {/* Halo */}
        <span
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
          style={{ height: u.size, width: u.size }}
        >
          <span
            className={
              u.pulse
                ? 'frise-halo-pulse block h-full w-full rounded-full'
                : 'block h-full w-full rounded-full opacity-0 transition-all duration-300 group-hover:scale-[1.9] group-hover:opacity-100'
            }
            style={{ background: u.ring, ...(u.pulse ? { opacity: 0.4 } : {}) }}
          />
        </span>

        {/* Nœud */}
        <span
          className="absolute left-1/2 top-1/2 z-10 -translate-x-1/2 -translate-y-1/2"
          style={{ height: u.size, width: u.size }}
        >
          <span
            className="frise-pop block h-full w-full rounded-full transition-transform duration-300 group-hover:scale-125"
            style={{
              background: u.filled ? u.node : C.card,
              border: u.filled ? 'none' : `2px solid ${u.node}`,
              boxShadow: `0 0 0 3px ${C.card}`,
              transformOrigin: 'center',
              animationDelay: `${index * 80}ms`,
            }}
          />
        </span>
      </span>

      {/* Contenu — seul élément teinté au survol (le rail/tracé reste intact) */}
      <span className="flex min-w-0 flex-1 flex-col gap-0.5 rounded-lg px-2.5 py-1.5 transition-colors duration-200 group-hover:bg-[var(--tint)]">
        <span className="flex items-center gap-2">
          <span className="min-w-0 flex-1 truncate text-[12.5px] font-medium" style={{ color: C.ink }}>
            {row.label}
          </span>
          <span
            className="shrink-0 rounded-full px-2 py-0.5 text-[10.5px] font-semibold tabular-nums"
            style={{ background: u.tint, color: u.fg }}
          >
            {row.badge}
          </span>
        </span>
        <span className="flex items-center gap-1 text-[11px]" style={{ color: C.ink, opacity: 0.55 }}>
          <Icon className="h-3 w-3 shrink-0" aria-hidden />
          <span className="truncate">{row.sub}</span>
          {row.to && (
            <ChevronRight
              className="ml-auto h-3.5 w-3.5 shrink-0 -translate-x-1 opacity-0 transition-all duration-200 group-hover:translate-x-0 group-hover:opacity-60"
              aria-hidden
            />
          )}
        </span>
      </span>
    </span>
  );

  return <li>{row.to ? <Link to={row.to}>{inner}</Link> : inner}</li>;
}
