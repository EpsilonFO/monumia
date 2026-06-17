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
  for (const d of deadlines.filter((x) => x.joursRestants >= 0)) {
    const { urgency } = deadlineLabel(d.date);
    const kind: FeedKind =
      urgency === 'urgent' ? 'urgent' : urgency === 'warning' ? 'warning' : 'info';
    rows.push({
      id: `deadline-${d.id}`,
      kind,
      icon: d.source === 'aide' ? Sparkles : FileText,
      label: d.label,
      sub: `${d.source === 'aide' ? 'Aide' : 'Dossier'} · ${formatDateShort(d.date)}`,
      badge: joursBadge(d),
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
