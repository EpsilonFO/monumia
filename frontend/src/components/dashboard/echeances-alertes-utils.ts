import { type ComponentType } from 'react';
import { IconNotification, IconAide, IconDocument } from '@/components/icons';
import i18n from '@/i18n';
import { deadlineLabel, formatRelative, formatDateShort } from '@/lib/date-utils';
import { deadlineLink } from '@/lib/project-stats';
import type { Notification } from '@/types';
import type { ProjectDeadline } from '@/lib/project-stats';

export type FeedKind = 'urgent' | 'warning' | 'info';

export interface FeedRow {
  id: string;
  kind: FeedKind;
  category: 'deadline' | 'notif';
  days?: number; // joursRestants pour les échéances ; undefined sinon
  icon: ComponentType<{ size?: number; className?: string }>;
  label: string; // titre principal
  sub: string; // ligne secondaire
  badge: string; // pastille à droite : "J-3" | "Auj." | "En retard" | "Nouveau"
  to?: string; // lien éventuel
  rank: number; // rang d'urgence pour le tri : urgent=0, warning=1, info=2
  sortKey: number; // tri secondaire au sein d'un même rang
}

const RANK: Record<FeedKind, number> = { urgent: 0, warning: 1, info: 2 };

function joursBadge(d: ProjectDeadline): string {
  return d.joursRestants === 0
    ? i18n.t('dashboard:echeancesAlertes.aujourdhui')
    : i18n.t('dashboard:echeancesAlertes.jours', { count: d.joursRestants });
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
      icon: d.source === 'aide' ? IconAide : IconDocument,
      label: d.label,
      sub:
        d.source === 'aide'
          ? i18n.t('dashboard:echeancesAlertes.sousAide', { date: formatDateShort(d.date) })
          : i18n.t('dashboard:echeancesAlertes.sousDossier', { date: formatDateShort(d.date) }),
      badge: d.joursRestants < 0 ? i18n.t('dashboard:echeancesAlertes.enRetard') : joursBadge(d),
      to: deadlineLink(d),
      rank: RANK[kind],
      sortKey: d.joursRestants,
    });
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
        icon: IconNotification,
        label: n.titre,
        sub: formatRelative(n.dateCreation),
        badge: i18n.t('dashboard:echeancesAlertes.nouveau'),
        rank: RANK[kind],
        sortKey: 1_000 + i,
      });
    });

  // Tri : rang d'urgence, puis clé secondaire (date / position)
  return rows.sort((a, b) => a.rank - b.rank || a.sortKey - b.sortKey);
}

/**
 * Flux agenda pour la section « Ensuite » de la carte unifiée : le flux complet
 * (échéances + notifications) moins les échéances déjà affichées dans le bloc
 * principal de la carte. Pur — exporté pour les tests unitaires.
 */
export function buildUpcomingRows(
  deadlines: ProjectDeadline[],
  shownDeadlines: ProjectDeadline[],
  notifications: Notification[]
): FeedRow[] {
  const shownIds = new Set(shownDeadlines.map((d) => d.id));
  return buildFeedRows(
    deadlines.filter((d) => !shownIds.has(d.id)),
    notifications
  );
}
