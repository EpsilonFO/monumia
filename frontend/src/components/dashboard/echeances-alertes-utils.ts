import {
  CalendarClock, Bell, ShieldAlert, Sparkles, FileText,
} from 'lucide-react';
import { ROUTES } from '@/constants/routes';
import { deadlineLabel, formatRelative, formatDateShort } from '@/lib/date-utils';
import { deadlineLink } from '@/lib/project-stats';
import type { Monument, Notification } from '@/types';
import type { ProjectDeadline } from '@/lib/project-stats';

export type FeedKind = 'urgent' | 'warning' | 'info';

export interface FeedRow {
  id: string;
  kind: FeedKind;
  category: 'deadline' | 'peril' | 'notif';
  days?: number; // joursRestants pour les échéances ; undefined sinon
  icon: typeof CalendarClock;
  label: string; // titre principal
  sub: string; // ligne secondaire
  badge: string; // pastille à droite : "J-3" | "Auj." | "Péril" | "68%" | "Nouveau"
  to?: string; // lien éventuel
  rank: number; // rang d'urgence pour le tri : urgent=0, warning=1, info=2
  sortKey: number; // tri secondaire au sein d'un même rang
}

const RANK: Record<FeedKind, number> = { urgent: 0, warning: 1, info: 2 };

function joursBadge(d: ProjectDeadline): string {
  return d.joursRestants === 0 ? 'Auj.' : `J-${d.joursRestants}`;
}

/**
 * Agrège échéances + alertes en un flux unique trié (rang d'urgence, puis date).
 * Fusionne l'ancien « Échéancier global » (TimelineStrip) et l'ancienne carte
 * « Alertes » (AlertsPanel) qui affichaient la même information dédoublée.
 *
 * Logique pure — exportée pour les tests unitaires. Le plafond d'affichage et le
 * « + N autres » sont gérés par le composant.
 */
export function buildFeedRows(
  deadlines: ProjectDeadline[],
  monuments: Monument[],
  notifications: Notification[]
): FeedRow[] {
  const rows: FeedRow[] = [];

  // Échéances à venir — toutes celles passées en entrée, sans aucun plafond :
  // l'échéancier les reprend toutes, même très éloignées dans le temps.
  for (const d of deadlines.filter((x) => x.joursRestants >= 0 || x.source === 'dossier')) {
    const { urgency } = deadlineLabel(d.date);
    const kind: FeedKind =
      urgency === 'past' || urgency === 'urgent' ? 'urgent' : urgency === 'warning' ? 'warning' : 'info';
    rows.push({
      id: `deadline-${d.id}`,
      kind,
      category: 'deadline',
      days: d.joursRestants,
      icon: d.source === 'aide' ? Sparkles : FileText,
      label: d.label,
      sub: `${d.source === 'aide' ? 'Aide' : 'Dossier'} · ${formatDateShort(d.date)}`,
      badge: d.joursRestants < 0 ? 'En retard' : joursBadge(d),
      to: deadlineLink(d),
      rank: RANK[kind],
      sortKey: d.joursRestants,
    });
  }

  // Monuments en péril / urgence critique — en tête du groupe urgent
  const perilIds = new Set<string>();
  for (const m of monuments) {
    if (m.etatConservation === 'peril' || m.urgenceTravaux === 'critique') {
      perilIds.add(m.id);
      rows.push({
        id: `peril-${m.id}`,
        kind: 'urgent',
        category: 'peril',
        icon: ShieldAlert,
        label: m.nom,
        sub: m.etatConservation === 'peril' ? 'État en péril' : 'Travaux urgents (critique)',
        badge: 'Péril',
        to: ROUTES.PROJET_DETAIL(m.id),
        rank: RANK.urgent,
        sortKey: -1,
      });
    }
  }

  // Notifications non lues (max 3, déjà triées par récence en amont)
  notifications
    .filter((n) => !n.lue)
    .slice(0, 3)
    .forEach((n, i) => {
      const kind: FeedKind = n.type === 'urgent' ? 'urgent' : 'info';
      rows.push({
        id: `notif-${n.id}`,
        kind,
        category: 'notif',
        icon: Bell,
        label: n.titre,
        sub: formatRelative(n.dateCreation),
        badge: 'Nouveau',
        rank: RANK[kind],
        sortKey: 1_000 + i,
      });
    });

  // Tri : rang d'urgence, puis clé secondaire (date / position)
  return rows.sort((a, b) => a.rank - b.rank || a.sortKey - b.sortKey);
}

export type HorizonKey = 'retard' | 'semaine' | 'mois' | 'plus_tard' | 'alertes';

export interface FeedGroup {
  key: HorizonKey;
  title: string;
  rows: FeedRow[];
}

const HORIZON_ORDER: { key: HorizonKey; title: string }[] = [
  { key: 'retard', title: 'En retard' },
  { key: 'semaine', title: 'Cette semaine' },
  { key: 'mois', title: 'Ce mois-ci' },
  { key: 'plus_tard', title: 'Plus tard' },
  { key: 'alertes', title: 'À noter' },
];

function horizonOf(row: FeedRow): HorizonKey {
  if (row.category === 'peril') return 'semaine';
  if (row.category === 'notif') return 'alertes';
  const d = row.days ?? 0;
  if (d < 0) return 'retard';
  if (d <= 7) return 'semaine';
  if (d <= 31) return 'mois';
  return 'plus_tard';
}

/** Regroupe le flux (sorti de buildFeedRows, déjà trié) par horizon temporel. Pur. */
export function groupFeedByHorizon(rows: FeedRow[]): FeedGroup[] {
  const buckets = new Map<HorizonKey, FeedRow[]>();
  for (const row of rows) {
    const key = horizonOf(row);
    const arr = buckets.get(key) ?? [];
    arr.push(row);
    buckets.set(key, arr);
  }
  return HORIZON_ORDER.map(({ key, title }) => ({ key, title, rows: buckets.get(key) ?? [] })).filter(
    (g) => g.rows.length > 0
  );
}
