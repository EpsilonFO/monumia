import type { Monument, Aide, AideMatchResult, AideDiagnosticResult, User, WorkType } from '@/types';
import { PROTECTION_LEVELS, OWNERSHIP_TYPES, WORK_TYPES, ETATS_CONSERVATION } from '@/constants/monument-options';

interface MatchContext {
  monument: Monument;
  user: User;
  modeProjet: boolean;
  travauxFiltres?: WorkType[];
}

function protectionLabel(value: string): string {
  return PROTECTION_LEVELS.find(p => p.value === value)?.label ?? value;
}

function ownerLabel(value: string): string {
  return OWNERSHIP_TYPES.find(o => o.value === value)?.label ?? value;
}

function workLabel(value: string): string {
  return WORK_TYPES.find(w => w.value === value)?.label ?? value;
}

function etatLabel(value: string): string {
  return ETATS_CONSERVATION.find(e => e.value === value)?.label ?? value;
}

function checkEligibility(aide: Aide, ctx: MatchContext): AideMatchResult {
  const criteresRemplis: string[] = [];
  const criteresNonRemplis: string[] = [];
  const { monument, user } = ctx;
  const c = aide.criteres;

  // Check protection level
  if (c.protectionRequise && c.protectionRequise.length > 0) {
    if (c.protectionRequise.includes(monument.protection)) {
      criteresRemplis.push(`Protection : ${protectionLabel(monument.protection)}`);
    } else {
      criteresNonRemplis.push(`Protection requise : ${c.protectionRequise.map(protectionLabel).join(', ')}`);
    }
  } else {
    criteresRemplis.push('Tous niveaux de protection');
  }

  // Check owner type
  if (c.proprietaireEligible && c.proprietaireEligible.length > 0) {
    if (c.proprietaireEligible.includes(monument.proprietaire)) {
      criteresRemplis.push(`Type de propriétaire : ${ownerLabel(monument.proprietaire)}`);
    } else {
      criteresNonRemplis.push(`Propriétaire éligible : ${c.proprietaireEligible.map(ownerLabel).join(', ')}`);
    }
  } else {
    criteresRemplis.push('Tous types de propriétaires');
  }

  // Check work types (only in project mode or if monument has travauxEnvisages)
  if (c.travauxEligibles && c.travauxEligibles.length > 0) {
    const travauxToCheck = ctx.modeProjet && ctx.travauxFiltres
      ? ctx.travauxFiltres
      : monument.travauxEnvisages ?? [];

    if (travauxToCheck.length === 0) {
      criteresRemplis.push('Types de travaux : non spécifiés (compatible)');
    } else {
      const match = travauxToCheck.some(t => c.travauxEligibles!.includes(t));
      if (match) {
        criteresRemplis.push('Types de travaux compatibles');
      } else {
        criteresNonRemplis.push(`Travaux éligibles : ${c.travauxEligibles.map(workLabel).join(', ')}`);
      }
    }
  } else {
    criteresRemplis.push('Tous types de travaux');
  }

  // Check region
  if (c.regionEligible && c.regionEligible.length > 0) {
    if (monument.region && c.regionEligible.includes(monument.region)) {
      criteresRemplis.push(`Région : ${monument.region}`);
    } else {
      criteresNonRemplis.push(`Région requise : ${c.regionEligible.join(', ')}`);
    }
  } else {
    criteresRemplis.push('Toute la France');
  }

  // Check department
  if (c.departementEligible && c.departementEligible.length > 0) {
    if (monument.departement && c.departementEligible.includes(monument.departement)) {
      criteresRemplis.push(`Département : ${monument.departement}`);
    } else {
      criteresNonRemplis.push(`Département requis : ${c.departementEligible.join(', ')}`);
    }
  }

  // Check commune population (flexible threshold)
  const maxPop = c.communeMaxPopulation ?? (c.communeDeMoins10000Hab ? 10000 : undefined);
  if (maxPop !== undefined) {
    if (user.segment === 'commune' && user.commune && user.commune.population < maxPop) {
      criteresRemplis.push(`Commune < ${maxPop.toLocaleString('fr-FR')} hab. (${user.commune.population} hab.)`);
    } else if (user.segment === 'commune' && user.commune && user.commune.population >= maxPop) {
      criteresNonRemplis.push(`Réservé aux communes < ${maxPop.toLocaleString('fr-FR')} hab.`);
    } else if (user.segment !== 'commune' && c.communeDeMoins10000Hab) {
      criteresNonRemplis.push('Réservé aux communes');
    }
  }

  // Check conservation state
  if (c.etatConservationRequis && c.etatConservationRequis.length > 0) {
    if (c.etatConservationRequis.includes(monument.etatConservation)) {
      criteresRemplis.push(`État de conservation : ${etatLabel(monument.etatConservation)}`);
    } else {
      criteresNonRemplis.push(`État requis : ${c.etatConservationRequis.map(etatLabel).join(', ')}`);
    }
  }

  const eligible = criteresNonRemplis.length === 0;

  return {
    aide,
    eligible,
    criteresRemplis,
    criteresNonRemplis,
    raisonIneligibilite: eligible
      ? undefined
      : criteresNonRemplis[0],
  };
}

export function runDiagnostic(
  monument: Monument,
  user: User,
  aides: Aide[],
  modeProjet: boolean = false,
  travauxFiltres?: WorkType[],
): AideDiagnosticResult {
  const ctx: MatchContext = { monument, user, modeProjet, travauxFiltres };

  const results = aides.map(aide => checkEligibility(aide, ctx));

  const aidesEligibles = results.filter(r => r.eligible);
  const aidesNonEligibles = results.filter(r => !r.eligible);

  const montantPotentielTotal = aidesEligibles.reduce((sum, r) => {
    if (r.aide.montantMax) return sum + r.aide.montantMax;
    if (r.aide.tauxMax && monument.travauxEnvisages) {
      // Rough estimate based on a typical project cost
      return sum;
    }
    return sum;
  }, 0);

  return {
    monumentId: monument.id,
    timestamp: new Date().toISOString(),
    totalAidesAnalysees: aides.length,
    aidesEligibles,
    aidesPotentiellementEligibles: [],
    aidesNonEligibles,
    montantPotentielTotal: montantPotentielTotal > 0 ? montantPotentielTotal : undefined,
  };
}
