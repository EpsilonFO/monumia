import type { ComponentType } from 'react';
import { IconSucces, IconErreur, IconHelp, IconCle, IconCalendrier } from '@/components/icons';
import type { AideDisponibilite, AideMatchResult, AideStatut } from '@/types';

/**
 * Statut d'éligibilité affichable, partagé par le bandeau, le badge et les
 * cartes. `atteignable` (« à débloquer ») est la nuance qui manquait : une aide
 * bloquée sur un seul critère actionnable n'est pas un refus, c'est une
 * démarche à engager.
 */
export type EligibilityStatus = 'eligible' | 'potential' | 'atteignable' | 'non-eligible';

const STATUT_TO_STATUS: Record<AideStatut, EligibilityStatus> = {
  eligible: 'eligible',
  atteignable: 'atteignable',
  potentiel: 'potential',
  non_eligible: 'non-eligible',
};

/**
 * Le moteur donne le statut explicitement (`statut`) : c'est la seule source qui
 * distingue « à débloquer » de « non éligible ». La dérivation depuis
 * `eligible` + incertitudes ne sert que de repli, si le champ manque.
 */
export function getEligibilityStatus(matchResult: AideMatchResult): EligibilityStatus {
  const fromEngine = matchResult.statut && STATUT_TO_STATUS[matchResult.statut];
  if (fromEngine) return fromEngine;
  const hasPendingIncertitudes = matchResult.llmEvaluation?.incertitudes?.some(
    (inc) => typeof inc === 'string' || !inc.clarified,
  );
  return matchResult.eligible && hasPendingIncertitudes
    ? 'potential'
    : matchResult.eligible
      ? 'eligible'
      : 'non-eligible';
}

/**
 * Fenêtre de candidature du jour, orthogonale au statut. Retombe sur
 * « maintenant » quand le moteur ne la renseigne pas, ce qui évite de marquer
 * une aide « ouvre bientôt » à tort.
 */
export function getDisponibilite(matchResult: {
  disponibilite?: AideDisponibilite;
}): AideDisponibilite {
  return matchResult.disponibilite ?? 'maintenant';
}

type StatusIcon = ComponentType<{ className?: string; strokeWidth?: number }>;

/**
 * Pastille « Ouvre bientôt » : même teinte info que « à débloquer » — dans les
 * deux cas l'aide reste une piste, c'est juste le moment qui n'est pas venu.
 * Rien de rouge : une session passée n'est pas une échéance manquée.
 */
export const DISPONIBILITE_BIENTOT_PILL = {
  label: 'Ouvre bientôt',
  icon: IconCalendrier as StatusIcon,
  /** Variante `Badge variant="outline"` (vignettes). */
  className: 'border-info text-info bg-info-muted',
  /** Variante pastille à pré-point coloré (cartes hero et grid). */
  tint: 'var(--info-muted)',
  accent: 'var(--info)',
} as const;

/** Badge de statut : classes token, libellé complet, icône. */
export const STATUS_BADGE: Record<
  EligibilityStatus,
  { className: string; label: string; icon: StatusIcon }
> = {
  eligible: {
    className: 'border-success text-success bg-success-muted',
    label: 'Éligible',
    icon: IconSucces,
  },
  atteignable: {
    className: 'border-info text-info bg-info-muted',
    label: 'À débloquer',
    icon: IconCle,
  },
  potential: {
    className: 'border-warning text-warning bg-warning-muted',
    label: 'Potentiellement éligible',
    icon: IconHelp,
  },
  'non-eligible': {
    className: 'border-destructive text-destructive bg-destructive-muted',
    label: 'Non éligible',
    icon: IconErreur,
  },
};

/** Teinte de la pastille ronde des cartes d'aide. */
export const STATUS_TONE: Record<EligibilityStatus, { tint: string; accent: string }> = {
  eligible: { tint: 'var(--success-muted)', accent: 'var(--success)' },
  atteignable: { tint: 'var(--info-muted)', accent: 'var(--info)' },
  potential: { tint: 'var(--warning-muted)', accent: 'var(--warning)' },
  'non-eligible': { tint: 'var(--destructive-muted)', accent: 'var(--destructive)' },
};

/** Libellé court de la pastille : « À confirmer » se lit mieux que « Potentiellement éligible ». */
export const STATUS_PILL_LABEL: Record<EligibilityStatus, string> = {
  eligible: 'Éligible',
  atteignable: 'À débloquer',
  potential: 'À confirmer',
  'non-eligible': 'Non éligible',
};
