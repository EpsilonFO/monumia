import i18n from '@/i18n';
import { localeIntl } from '@/i18n/format';

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat(localeIntl(), {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatPercentage(value: number): string {
  const formatted = new Intl.NumberFormat(localeIntl(), {
    maximumFractionDigits: 1,
  }).format(value);
  return i18n.t('core:formatUtils.pourcentage', { valeur: formatted });
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return i18n.t('core:formatUtils.octets', { taille: bytes });
  if (bytes < 1024 * 1024) return i18n.t('core:formatUtils.kilooctets', { taille: (bytes / 1024).toFixed(1) });
  return i18n.t('core:formatUtils.megaoctets', { taille: (bytes / (1024 * 1024)).toFixed(1) });
}

export function formatShortDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return new Intl.DateTimeFormat(localeIntl(), { day: 'numeric', month: 'short', year: 'numeric' }).format(d);
}

export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trim() + '…';
}

export function generateId(): string {
  return Math.random().toString(36).substring(2, 11);
}
