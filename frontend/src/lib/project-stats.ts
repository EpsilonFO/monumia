import { daysUntil, deadlineLabel } from '@/lib/date-utils';
import { ROUTES } from '@/constants/routes';
import type { Monument } from '@/types';
import type { AideDiagnosticResult, AideMatchResult } from '@/types';
import type { Dossier } from '@/types';
import type { AideSuivi } from '@/types';

export interface ProjectDeadline {
  id: string;
  label: string;
  date: string;
  source: 'aide' | 'dossier';
  joursRestants: number;
  urgency: 'normal' | 'warning' | 'urgent' | 'past';
  monumentId?: string;
  aideId?: string;
  dossierId?: string;
}

/**
 * Destination d'un clic sur une échéance — la page de l'aide concernée :
 *  - échéance d'aide   → page de l'aide (onglet Description par défaut) ;
 *  - échéance de dossier → le dossier correspondant.
 * Repli sur le projet, puis la liste des projets, si l'on manque d'identifiants.
 */
export function deadlineLink(d: ProjectDeadline): string {
  if (d.source === 'aide' && d.monumentId && d.aideId) {
    return ROUTES.PROJET_AIDE(d.monumentId, d.aideId);
  }
  if (d.monumentId && d.dossierId) return ROUTES.PROJET_DOSSIER(d.monumentId, d.dossierId);
  if (d.dossierId) return ROUTES.DOSSIER_DETAIL(d.dossierId);
  if (d.monumentId) return ROUTES.PROJET_DETAIL(d.monumentId);
  return ROUTES.PROJETS;
}

/**
 * Build the unified deadline list for a project:
 *  - aide `dateLimite` from eligibles + potentiels, only when `!permanent` and a date exists;
 *    past aide deadlines are dropped (irrelevant — the window closed).
 *  - dossier `echeances` that are not `accomplie`; past dossier echeances are KEPT as 'past'
 *    (the user still has an overdue task to act on).
 * Sorted ascending by `joursRestants`.
 */
export function mergeProjectDeadlines(
  diagnostic: AideDiagnosticResult | null,
  dossiers: Dossier[]
): ProjectDeadline[] {
  const deadlines: ProjectDeadline[] = [];

  if (diagnostic) {
    const matches: AideMatchResult[] = [
      ...diagnostic.aidesEligibles,
      ...diagnostic.aidesPotentiellementEligibles,
    ];
    for (const match of matches) {
      const aide = match.aide;
      if (aide.permanent || !aide.dateLimite) continue;
      const joursRestants = daysUntil(aide.dateLimite);
      if (joursRestants < 0) continue; // drop past aides
      deadlines.push({
        id: `aide-${aide.id}`,
        label: aide.nom,
        date: aide.dateLimite,
        source: 'aide',
        joursRestants,
        urgency: deadlineLabel(aide.dateLimite).urgency,
        monumentId: diagnostic.monumentId,
        aideId: aide.id,
      });
    }
  }

  for (const dossier of dossiers) {
    for (const echeance of dossier.echeances) {
      if (echeance.accomplie) continue;
      const joursRestants = daysUntil(echeance.date);
      deadlines.push({
        id: `dossier-${dossier.id}-${echeance.id}`,
        label: echeance.label,
        date: echeance.date,
        source: 'dossier',
        joursRestants,
        urgency: deadlineLabel(echeance.date).urgency,
        monumentId: dossier.monumentId,
        dossierId: dossier.id,
      });
    }
  }

  return deadlines.sort((a, b) => a.joursRestants - b.joursRestants);
}

export interface ProjectStats {
  aidesIdentifiees: number;
  montantPotentiel: number;
  dossiersActifs: number;
  prochaineEcheance: ProjectDeadline | null;
  completion: number;
}

export function computeProjectStats(
  monument: Monument,
  diagnostic: AideDiagnosticResult | null,
  dossiers: Dossier[]
): ProjectStats {
  const aidesIdentifiees = diagnostic
    ? diagnostic.aidesEligibles.length + diagnostic.aidesPotentiellementEligibles.length
    : 0;
  const montantPotentiel = diagnostic?.montantPotentielTotal ?? 0;

  const monumentDossiers = dossiers.filter((d) => d.monumentId === monument.id);
  const dossiersActifs = monumentDossiers.filter((d) => d.statut !== 'soumis').length;

  const prochaineEcheance =
    mergeProjectDeadlines(diagnostic, monumentDossiers).find((d) => d.joursRestants >= 0) ?? null;

  return {
    aidesIdentifiees,
    montantPotentiel,
    dossiersActifs,
    prochaineEcheance,
    completion: monument.completionPercentage,
  };
}

export interface DashboardStats {
  projetsActifs: number;
  aidesIdentifiees: number;
  montantPotentielTotal: number;
  dossiersEnCours: number;
  prochaineEcheance: ProjectDeadline | null;
  aidesParCategorie: { categorie: string; count: number }[];
  montantParProjet: { nom: string; montant: number }[];
}

export function aggregateDashboardStats(
  monuments: Monument[],
  diagnosticsByMonument: Record<string, AideDiagnosticResult | null>,
  dossiers: Dossier[]
): DashboardStats {
  let aidesIdentifiees = 0;
  let montantPotentielTotal = 0;
  const categorieCounts = new Map<string, number>();
  const montantParProjet: { nom: string; montant: number }[] = [];
  const allDeadlines: ProjectDeadline[] = [];

  for (const monument of monuments) {
    const diagnostic = diagnosticsByMonument[monument.id] ?? null;
    const monumentDossiers = dossiers.filter((d) => d.monumentId === monument.id);

    if (diagnostic) {
      const matches: AideMatchResult[] = [
        ...diagnostic.aidesEligibles,
        ...diagnostic.aidesPotentiellementEligibles,
      ];
      aidesIdentifiees += matches.length;
      montantPotentielTotal += diagnostic.montantPotentielTotal ?? 0;
      for (const match of matches) {
        const categorie = match.aide.categorie;
        categorieCounts.set(categorie, (categorieCounts.get(categorie) ?? 0) + 1);
      }
    }

    montantParProjet.push({
      nom: monument.nom,
      montant: diagnostic?.montantPotentielTotal ?? 0,
    });

    allDeadlines.push(...mergeProjectDeadlines(diagnostic, monumentDossiers));
  }

  const dossiersEnCours = dossiers.filter((d) => d.statut !== 'soumis').length;

  const prochaineEcheance =
    allDeadlines
      .filter((d) => d.joursRestants >= 0)
      .sort((a, b) => a.joursRestants - b.joursRestants)[0] ?? null;

  const aidesParCategorie = Array.from(categorieCounts.entries())
    .map(([categorie, count]) => ({ categorie, count }))
    .sort((a, b) => b.count - a.count);

  return {
    projetsActifs: monuments.length,
    aidesIdentifiees,
    montantPotentielTotal,
    dossiersEnCours,
    prochaineEcheance,
    aidesParCategorie,
    montantParProjet,
  };
}

export type ProjectStageKey = 'estimation' | 'dossier' | 'depot' | 'suivi';

export const PROJECT_STAGES: { key: ProjectStageKey; label: string }[] = [
  { key: 'estimation', label: 'Estimation' },
  { key: 'dossier', label: 'Dossier' },
  { key: 'depot', label: 'Dépôt' },
  { key: 'suivi', label: 'Suivi' },
];

export interface ProjectStage {
  /** Index (0..3) de l'étape la plus avancée atteinte ; -1 si rien. */
  reachedIndex: number;
  reached: ProjectStageKey[];
  /** Étape mise en avant (la plus avancée atteinte, ou « estimation » si rien). */
  current: ProjectStageKey;
}

/**
 * Étape de parcours d'un projet, dérivée de l'état existant (fonction pure).
 * Monotone : une étape avancée implique les précédentes comme atteintes.
 */
export function projectStage(
  diagnostic: AideDiagnosticResult | null,
  dossiers: Dossier[],
  suivis: AideSuivi[]
): ProjectStage {
  const raw = [
    !!diagnostic, // estimation
    dossiers.length > 0, // dossier
    dossiers.some((d) => d.statut === 'pret' || d.statut === 'soumis'), // dépôt
    suivis.some((s) => s.statut === 'depose' || s.statut === 'accorde' || s.statut === 'refuse'), // suivi
  ];

  let reachedIndex = -1;
  for (let i = 0; i < raw.length; i++) {
    if (raw[i]) reachedIndex = i;
  }

  return {
    reachedIndex,
    reached: PROJECT_STAGES.slice(0, reachedIndex + 1).map((s) => s.key),
    current: PROJECT_STAGES[Math.max(reachedIndex, 0)].key,
  };
}
