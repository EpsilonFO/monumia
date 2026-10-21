import { format, formatDistanceToNow, differenceInDays, parseISO } from 'date-fns';
import i18n from '@/i18n';
import { localeDateFns } from '@/i18n/format';

export function formatDate(date: string | Date): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  return format(d, 'dd MMMM yyyy', { locale: localeDateFns() });
}

export function formatDateShort(date: string | Date): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  return format(d, 'dd/MM/yyyy', { locale: localeDateFns() });
}

export function formatRelative(date: string | Date): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  return formatDistanceToNow(d, { addSuffix: true, locale: localeDateFns() });
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
  if (days < 0) return { text: i18n.t('core:dateUtils.echeanceDepassee'), urgency: 'past' };
  if (days === 0) return { text: i18n.t('core:dateUtils.aujourdhui'), urgency: 'urgent' };
  if (days === 1) return { text: i18n.t('core:dateUtils.demain'), urgency: 'urgent' };
  if (days < 30) return { text: i18n.t('core:dateUtils.dansNJours', { count: days }), urgency: 'urgent' };
  if (days <= 100) return { text: i18n.t('core:dateUtils.dansNJours', { count: days }), urgency: 'warning' };
  return { text: formatDateShort(date), urgency: 'normal' };
}
