import { format, formatDistanceToNow, differenceInDays, parseISO } from 'date-fns';
import { fr } from 'date-fns/locale';

export function formatDate(date: string | Date): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  return format(d, 'dd MMMM yyyy', { locale: fr });
}

export function formatDateShort(date: string | Date): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  return format(d, 'dd/MM/yyyy', { locale: fr });
}

export function formatRelative(date: string | Date): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  return formatDistanceToNow(d, { addSuffix: true, locale: fr });
}

export function daysUntil(date: string | Date): number {
  const d = typeof date === 'string' ? parseISO(date) : date;
  return differenceInDays(d, new Date());
}

export function isUrgent(date: string | Date, thresholdDays = 30): boolean {
  return daysUntil(date) <= thresholdDays && daysUntil(date) >= 0;
}

export function deadlineLabel(date: string | Date): { text: string; urgency: 'normal' | 'warning' | 'urgent' | 'past' } {
  const days = daysUntil(date);
  if (days < 0) return { text: 'Échéance dépassée', urgency: 'past' };
  if (days === 0) return { text: "Aujourd'hui", urgency: 'urgent' };
  if (days === 1) return { text: 'Demain', urgency: 'urgent' };
  if (days <= 7) return { text: `Dans ${days} jours`, urgency: 'urgent' };
  if (days <= 30) return { text: `Dans ${days} jours`, urgency: 'warning' };
  return { text: formatDateShort(date), urgency: 'normal' };
}
