import type { AideSuiviStatut } from '@/types';
import { AIDE_SUIVI_STATUT_LABELS } from '@/types';

// Palette par statut d'avancement, partagée par le badge (carte dossier) et le
// sélecteur (page dossier).
export const AIDE_STATUT_PILL: Record<AideSuiviStatut, { bg: string; fg: string }> = {
  a_faire: { bg: '#f1f5f9', fg: '#475569' },
  en_preparation: { bg: '#eef2ff', fg: '#3730a3' },
  depose: { bg: '#fff7ed', fg: '#c2410c' },
  accorde: { bg: '#ecfdf5', fg: '#047857' },
  refuse: { bg: '#fef2f2', fg: '#b91c1c' },
};

export function AideStatutBadge({
  statut,
  className = '',
}: {
  statut: AideSuiviStatut;
  className?: string;
}) {
  const s = AIDE_STATUT_PILL[statut];
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold whitespace-nowrap ${className}`}
      style={{ background: s.bg, color: s.fg }}
    >
      {AIDE_SUIVI_STATUT_LABELS[statut]}
    </span>
  );
}
