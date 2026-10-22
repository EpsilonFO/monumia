import i18n from '@/i18n';
import { chapeauAide, montantAide, titreAide } from '@/lib/fiche-aide';
import type { ProjectDeadline } from '@/lib/project-stats';
import type { AideDigestMatch, Dossier, Monument, ProjectDigest } from '@/types';

/**
 * Ce qu'il reste à faire sur l'aide ou le dossier dont la date approche.
 *  - `questions` : l'aide est à confirmer et des questions la départagent ;
 *  - `verifier`  : à confirmer, mais aucune question n'y répond plus (des points
 *    que la fiche liste et que le moteur ne sait pas trancher) ;
 *  - `eligible`  : les conditions publiées sont remplies ;
 *  - `demarche`  : une démarche à faire avant le dépôt (« à débloquer ») ;
 *  - `dossier`   : l'échéance d'un dossier déjà ouvert.
 */
export type NatureAFaire = 'questions' | 'verifier' | 'eligible' | 'demarche' | 'dossier';

export interface AFaire {
  echeance: ProjectDeadline;
  nature: NatureAFaire;
  titre: string;
  /** Le montant écrit (« Jusqu'à 10 000 € »), s'il est publié. */
  montant: string | null;
  /** Le chapeau de l'aide, ou l'intitulé de l'échéance d'un dossier. */
  detail: string;
  monumentNom: string | null;
  /** Nombre de questions restantes (nature `questions`). */
  questions: number;
}

function trouverMatch(digest: ProjectDigest | null, aideId: string) {
  if (!digest) return null;
  const seaux: [AideDigestMatch[], 'eligible' | 'potentiel' | 'demarche'][] = [
    [digest.aidesEligibles, 'eligible'],
    [digest.aidesPotentiellementEligibles, 'potentiel'],
    [digest.aidesAtteignables ?? [], 'demarche'],
  ];
  for (const [matches, seau] of seaux) {
    const match = matches.find((m) => m.aide.id === aideId);
    if (match) return { match, seau };
  }
  return null;
}

/**
 * La première échéance de la liste (déjà triée, retards de dossier compris),
 * rédigée pour la carte « À faire maintenant » du tableau de bord. `null` s'il
 * n'y a rien de daté. Fonction pure.
 */
export function aFaireMaintenant(
  echeances: ProjectDeadline[],
  digests: Record<string, ProjectDigest | null>,
  dossiers: Dossier[],
  monuments: Monument[],
): AFaire | null {
  const echeance = echeances[0];
  if (!echeance) return null;
  const monumentNom = monuments.find((m) => m.id === echeance.monumentId)?.nom ?? null;

  if (echeance.source === 'dossier') {
    const dossier = dossiers.find((d) => d.id === echeance.dossierId);
    return {
      echeance,
      nature: 'dossier',
      titre: dossier?.titre || echeance.label,
      montant: null,
      detail: echeance.label,
      monumentNom,
      questions: 0,
    };
  }

  const trouve = echeance.aideId && echeance.projetId
    ? trouverMatch(digests[echeance.projetId] ?? null, echeance.aideId)
    : null;
  const aide = trouve?.match.aide;
  const questions = trouve?.match.questionsRestantes ?? 0;
  const nature: NatureAFaire =
    trouve?.seau === 'eligible'
      ? 'eligible'
      : trouve?.seau === 'demarche'
        ? 'demarche'
        : questions > 0
          ? 'questions'
          : 'verifier';

  return {
    echeance,
    nature,
    titre: aide ? titreAide(aide) : echeance.label,
    montant: aide ? (montantAide(aide)?.valeur ?? null) : null,
    detail: aide ? chapeauAide(aide) : '',
    monumentNom,
    questions,
  };
}

/** « dans 36 jours », « demain », « aujourd'hui », « en retard de 3 jours ». */
export function quandLibelle(joursRestants: number): string {
  if (joursRestants < 0) {
    return i18n.t('libAides:aFaireMaintenant.enRetard', { count: -joursRestants });
  }
  if (joursRestants === 0) return i18n.t('libAides:aFaireMaintenant.aujourdhui');
  if (joursRestants === 1) return i18n.t('libAides:aFaireMaintenant.demain');
  return i18n.t('libAides:aFaireMaintenant.dansJours', { count: joursRestants });
}
