import { daysUntil, deadlineLabel } from '@/lib/date-utils';
import { ROUTES } from '@/constants/routes';
import type { Monument, Projet } from '@/types';
import type { AideDigest, ProjectDigest } from '@/types';
import type { Dossier } from '@/types';
import type { AideSuivi } from '@/types';

export interface ProjectDeadline {
  id: string;
  label: string;
  date: string;
  source: 'aide' | 'dossier';
  joursRestants: number;
  urgency: 'normal' | 'warning' | 'urgent' | 'past';
  /** Le PROJET concerné : une échéance porte sur un chantier, pas sur le bien. */
  projetId?: string;
  /** Monument parent — repli quand le projet est inconnu (vieux lien, digest
   *  d'un chemin de compatibilité). */
  monumentId?: string;
  aideId?: string;
  dossierId?: string;
}

/**
 * Destination d'un clic sur une échéance — la page de l'aide concernée :
 *  - échéance d'aide   → page de l'aide (onglet Description par défaut) ;
 *  - échéance de dossier → le dossier correspondant.
 * Repli sur le projet, puis son monument, puis la liste, si l'on manque
 * d'identifiants.
 */
export function deadlineLink(d: ProjectDeadline): string {
  if (d.source === 'aide' && d.projetId && d.aideId) {
    return ROUTES.PROJET_AIDE(d.projetId, d.aideId);
  }
  if (d.projetId && d.dossierId) return ROUTES.PROJET_DOSSIER(d.projetId, d.dossierId);
  if (d.projetId) return ROUTES.PROJET_DETAIL(d.projetId);
  if (d.monumentId) return ROUTES.MONUMENT_DETAIL(d.monumentId);
  return ROUTES.MONUMENTS;
}

/**
 * Build the unified deadline list for a project:
 *  - aide `dateLimite` from eligibles + potentiels, only when `!permanent` and a date exists;
 *    past aide deadlines are dropped (irrelevant — the window closed).
 *  - dossier `echeances` that are not `accomplie` and not past either. Décision du
 *    2026-09-28 : une date passée ne s'affiche plus nulle part (tableau de bord,
 *    échéancier, cartes), elle n'est plus actionnable.
 * Sorted ascending by `joursRestants`.
 */
export function mergeProjectDeadlines(
  diagnostic: ProjectDigest | null,
  dossiers: Dossier[]
): ProjectDeadline[] {
  const deadlines: ProjectDeadline[] = [];

  if (diagnostic) {
    // Les aides à débloquer comptent aussi : leur date limite est bien réelle,
    // et c'est elle qui dit combien de temps il reste pour faire la démarche.
    const matches: { aide: AideDigest }[] = [
      ...diagnostic.aidesEligibles,
      ...diagnostic.aidesPotentiellementEligibles,
      ...(diagnostic.aidesAtteignables ?? []),
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
        projetId: diagnostic.projetId,
        monumentId: diagnostic.monumentId,
        aideId: aide.id,
      });
    }
  }

  for (const dossier of dossiers) {
    for (const echeance of dossier.echeances) {
      if (echeance.accomplie) continue;
      const joursRestants = daysUntil(echeance.date);
      if (joursRestants < 0) continue;
      deadlines.push({
        id: `dossier-${dossier.id}-${echeance.id}`,
        label: echeance.label,
        date: echeance.date,
        source: 'dossier',
        joursRestants,
        urgency: deadlineLabel(echeance.date).urgency,
        projetId: dossier.projetId,
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
  /** Montant des aides « à débloquer ». Compté à part : il n'est pas acquis. */
  montantAtteignable: number;
  /** Part maximale du coût des travaux couverte, en % (0 si aucune aide chiffrée
   *  en taux). Complète le montant : beaucoup d'aides ne plafonnent pas en euros.
   *  Périmètre plus large que `montantPotentiel` — les aides « à débloquer » y
   *  comptent, la case annonçant un maximum atteignable et non un acquis. */
  tauxTravauxMax: number;
  dossiersActifs: number;
  prochaineEcheance: ProjectDeadline | null;
}

/** Chiffres d'UN projet de travaux : ce que son en-tête et sa carte affichent. */
export function computeProjectStats(
  projet: Projet,
  diagnostic: ProjectDigest | null,
  dossiers: Dossier[]
): ProjectStats {
  const aidesIdentifiees = diagnostic
    ? diagnostic.aidesEligibles.length
      + diagnostic.aidesPotentiellementEligibles.length
      + (diagnostic.aidesAtteignables?.length ?? 0)
    : 0;
  // Le montant potentiel agrège les aides à portée sans démarche préalable :
  // « disponibles maintenant », « à confirmer » et « disponibles bientôt ».
  // Les aides « à débloquer » en restent exclues — elles supposent une démarche
  // encore à faire, et sont exposées séparément.
  const montantPotentiel = diagnostic?.montantPotentielTotal ?? 0;
  const montantAtteignable = diagnostic?.montantAtteignableTotal ?? 0;
  const tauxTravauxMax = diagnostic?.tauxTravauxMaxPct ?? 0;

  const projetDossiers = dossiers.filter((d) => d.projetId === projet.id);
  const dossiersActifs = projetDossiers.filter((d) => d.statut !== 'soumis').length;

  const prochaineEcheance =
    mergeProjectDeadlines(diagnostic, projetDossiers).find((d) => d.joursRestants >= 0) ?? null;

  return {
    aidesIdentifiees,
    montantPotentiel,
    montantAtteignable,
    tauxTravauxMax,
    dossiersActifs,
    prochaineEcheance,
  };
}

export interface MonumentStats {
  /** Nombre de projets de travaux ouverts sur ce monument. */
  projets: number;
  /** Aides repérées, tous projets confondus. */
  aidesIdentifiees: number;
  /** Somme des montants potentiels des projets. Deux projets peuvent viser la
   *  même aide : le total est donc un ordre de grandeur, pas un cumul exigible.
   *  Les aides « à débloquer » en restent exclues (démarche encore à faire). */
  montantPotentiel: number;
  dossiersActifs: number;
  prochaineEcheance: ProjectDeadline | null;
  /** Complétude de la FICHE du monument (pas des projets). */
  completion: number;
}

/**
 * Chiffres d'un MONUMENT : l'agrégat de ses projets. Fonction pure.
 *
 * Un monument sans projet rend des zéros et une échéance nulle — c'est ce qui
 * fait basculer sa carte sur le CTA « Lancer un projet de travaux » plutôt que
 * sur des montants.
 */
export function computeMonumentStats(
  monument: Monument,
  projets: Projet[],
  digestsByProjet: Record<string, ProjectDigest | null>,
  dossiers: Dossier[]
): MonumentStats {
  const mesProjets = projets.filter((p) => p.monumentId === monument.id);
  const mesDossiers = dossiers.filter((d) => d.monumentId === monument.id);

  let aidesIdentifiees = 0;
  let montantPotentiel = 0;
  const echeances: ProjectDeadline[] = [];

  for (const projet of mesProjets) {
    const stats = computeProjectStats(projet, digestsByProjet[projet.id] ?? null, mesDossiers);
    aidesIdentifiees += stats.aidesIdentifiees;
    montantPotentiel += stats.montantPotentiel;
    if (stats.prochaineEcheance) echeances.push(stats.prochaineEcheance);
  }

  return {
    projets: mesProjets.length,
    aidesIdentifiees,
    montantPotentiel,
    dossiersActifs: mesDossiers.filter((d) => d.statut !== 'soumis').length,
    prochaineEcheance:
      echeances.sort((a, b) => a.joursRestants - b.joursRestants)[0] ?? null,
    completion: monument.completionPercentage,
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
  diagnostic: ProjectDigest | null,
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
