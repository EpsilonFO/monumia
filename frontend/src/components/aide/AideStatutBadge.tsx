import type { AideSuiviStatut } from '@/types';
import { AIDE_SUIVI_STATUT_LABELS } from '@/types';

// Palette par statut d'avancement — classes token (bg + texte) partagées par le
// badge (carte dossier) et le sélecteur (page dossier).
export const AIDE_STATUT_STYLES: Record<AideSuiviStatut, string> = {
  a_faire:        'bg-muted text-muted-foreground',
  en_preparation: 'bg-info-muted text-info',
  depose:         'bg-warning-muted text-warning',
  accorde:        'bg-success-muted text-success',
  refuse:         'bg-destructive-muted text-destructive',
};

export function AideStatutBadge({
  statut,
  className = '',
}: {
  statut: AideSuiviStatut;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[13px] font-semibold whitespace-nowrap ${AIDE_STATUT_STYLES[statut]} ${className}`}
    >
      {AIDE_SUIVI_STATUT_LABELS[statut]}
    </span>
  );
}
