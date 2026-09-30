import { describe, expect, it } from 'vitest';
import {
  mergeProjectDeadlines,
  computeProjectStats,
  computeMonumentStats,
  projectStage,
  PROJECT_STAGES,
} from '@/lib/project-stats';
import type { Monument, Projet } from '@/types';
import type { Aide, AideDiagnosticResult, AideMatchResult } from '@/types';
import type { Dossier, DossierEcheance } from '@/types';
import type { AideSuivi } from '@/types';

// ---- ISO date helpers (relative to "now") ----
const iso = (offsetDays: number): string => {
  const d = new Date();
  d.setHours(12, 0, 0, 0);
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
};
const FAR_FUTURE = iso(400); // ~13 months out -> 'normal'
const NEAR_FUTURE = iso(5); // -> 'urgent'
const PAST = iso(-30); // -> 'past'

// ---- minimal builders ----
function makeAide(partial: Partial<Aide> & { id: string }): Aide {
  return {
    id: partial.id,
    nom: partial.nom ?? `Aide ${partial.id}`,
    nomCourt: partial.nomCourt ?? `Aide ${partial.id}`,
    description: '',
    descriptionLongue: '',
    categorie: partial.categorie ?? 'etat_drac',
    type: 'subvention',
    organisme: 'DRAC',
    montantMax: partial.montantMax,
    tauxMax: partial.tauxMax,
    criteres: {} as Aide['criteres'],
    demarcheDescription: '',
    documentsRequis: [],
    delaiInstruction: '',
    dateOuverture: partial.dateOuverture,
    dateLimite: partial.dateLimite,
    permanent: partial.permanent ?? false,
    urlOfficielle: partial.urlOfficielle,
    formulaireUrl: undefined,
    baseTTC: false,
  } as Aide;
}

function makeMatch(aide: Aide): AideMatchResult {
  return { aide, eligible: true, criteresRemplis: [], criteresNonRemplis: [] };
}

function makeDiagnostic(
  projetId: string,
  eligibles: AideMatchResult[],
  potentiels: AideMatchResult[],
  montant: number
): AideDiagnosticResult {
  return {
    projetId,
    monumentId: 'm1',
    timestamp: new Date().toISOString(),
    totalAidesAnalysees: eligibles.length + potentiels.length,
    aidesEligibles: eligibles,
    aidesPotentiellementEligibles: potentiels,
    aidesNonEligibles: [],
    montantPotentielTotal: montant,
  };
}

function makeEcheance(partial: Partial<DossierEcheance> & { id: string; date: string }): DossierEcheance {
  return {
    id: partial.id,
    label: partial.label ?? 'Échéance',
    date: partial.date,
    type: partial.type ?? 'limite',
    accomplie: partial.accomplie ?? false,
  };
}

function makeDossier(partial: Partial<Dossier> & { id: string; monumentId: string }): Dossier {
  return {
    id: partial.id,
    projetId: partial.projetId ?? 'p1',
    monumentId: partial.monumentId,
    aideId: partial.aideId ?? 'a1',
    userId: 'u1',
    titre: partial.titre ?? 'Dossier',
    etapeActuelle: 1,
    statut: partial.statut ?? 'en_cours',
    progressionPourcentage: 0,
    travauxPrevus: [],
    checklist: [],
    sections: [],
    echeances: partial.echeances ?? [],
    collaborateurs: [],
    dateCreation: new Date().toISOString(),
    dateDerniereModification: new Date().toISOString(),
  } as Dossier;
}

function makeProjet(partial: Partial<Projet> & { id: string }): Projet {
  return {
    id: partial.id,
    monumentId: partial.monumentId ?? 'm1',
    userId: 'u1',
    travauxEnvisages: partial.travauxEnvisages ?? null,
    questionnaire: partial.questionnaire ?? {},
    clotureAt: partial.clotureAt,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

function makeMonument(partial: Partial<Monument> & { id: string }): Monument {
  return {
    id: partial.id,
    userId: 'u1',
    nom: partial.nom ?? `Monument ${partial.id}`,
    codeInsee: '00000',
    protection: 'classe',
    proprietaire: ['public_commune'],
    etatConservation: 'moyen',
    photos: [],
    completionPercentage: partial.completionPercentage ?? 60,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  } as Monument;
}

describe('mergeProjectDeadlines', () => {
  it('merges non-permanent aide dateLimite + non-accomplished dossier echeances, sorted ascending', () => {
    const aideFar = makeAide({ id: 'aFar', dateLimite: FAR_FUTURE, permanent: false });
    const aideNear = makeAide({ id: 'aNear', dateLimite: NEAR_FUTURE, permanent: false });
    const diagnostic = makeDiagnostic('p1', [makeMatch(aideFar)], [makeMatch(aideNear)], 0);
    const dossier = makeDossier({
      id: 'd1',
      monumentId: 'm1',
      echeances: [makeEcheance({ id: 'e1', date: FAR_FUTURE, accomplie: false })],
    });

    const merged = mergeProjectDeadlines(diagnostic, [dossier]);

    expect(merged.map((d) => d.source)).toContain('aide');
    expect(merged.map((d) => d.source)).toContain('dossier');
    // sorted ascending by joursRestants -> the NEAR aide comes first
    expect(merged[0].source).toBe('aide');
    expect(merged[0].aideId).toBe('aNear');
    expect(merged[0].joursRestants).toBeLessThan(merged[1].joursRestants);
  });

  it('drops permanent aides and accomplished echeances', () => {
    const permanentAide = makeAide({ id: 'aPerm', dateLimite: NEAR_FUTURE, permanent: true });
    const datedAide = makeAide({ id: 'aDated', dateLimite: FAR_FUTURE, permanent: false });
    const diagnostic = makeDiagnostic('p1', [makeMatch(permanentAide), makeMatch(datedAide)], [], 0);
    const dossier = makeDossier({
      id: 'd1',
      monumentId: 'm1',
      echeances: [
        makeEcheance({ id: 'e1', date: NEAR_FUTURE, accomplie: true }),
        makeEcheance({ id: 'e2', date: FAR_FUTURE, accomplie: false }),
      ],
    });

    const merged = mergeProjectDeadlines(diagnostic, [dossier]);

    expect(merged.find((d) => d.aideId === 'aPerm')).toBeUndefined();
    expect(merged.find((d) => d.dossierId === 'd1' && d.id.includes('e1'))).toBeUndefined();
    expect(merged.some((d) => d.aideId === 'aDated')).toBe(true);
    expect(merged.some((d) => d.id.includes('e2'))).toBe(true);
  });

  it('drops past aides and past dossier echeances alike', () => {
    const pastAide = makeAide({ id: 'aPast', dateLimite: PAST, permanent: false });
    const diagnostic = makeDiagnostic('p1', [makeMatch(pastAide)], [], 0);
    const dossier = makeDossier({
      id: 'd1',
      monumentId: 'm1',
      echeances: [makeEcheance({ id: 'ePast', date: PAST, accomplie: false })],
    });

    const merged = mergeProjectDeadlines(diagnostic, [dossier]);

    expect(merged.find((d) => d.aideId === 'aPast')).toBeUndefined();
    expect(merged.find((d) => d.dossierId === 'd1')).toBeUndefined();
  });

  it('returns empty array when diagnostic is null and no dossiers', () => {
    expect(mergeProjectDeadlines(null, [])).toEqual([]);
  });
});

describe('computeProjectStats', () => {
  it('compte les aides, somme le montant, compte les dossiers actifs DU PROJET et prend la prochaine échéance', () => {
    const projet = makeProjet({ id: 'p1', monumentId: 'm1' });
    const aideElig = makeAide({ id: 'a1', dateLimite: NEAR_FUTURE, permanent: false });
    const aidePot = makeAide({ id: 'a2', dateLimite: FAR_FUTURE, permanent: false });
    const diagnostic = makeDiagnostic('p1', [makeMatch(aideElig)], [makeMatch(aidePot)], 125000);
    const dossiers = [
      makeDossier({ id: 'd1', projetId: 'p1', monumentId: 'm1', statut: 'en_cours' }),
      makeDossier({ id: 'd2', projetId: 'p1', monumentId: 'm1', statut: 'soumis' }), // pas actif
      makeDossier({ id: 'd3', projetId: 'p2', monumentId: 'm1', statut: 'en_cours' }), // autre PROJET du même monument
    ];

    const stats = computeProjectStats(projet, diagnostic, dossiers);

    expect(stats.aidesIdentifiees).toBe(2);
    expect(stats.montantPotentiel).toBe(125000);
    // Le dossier de l'autre projet du même monument ne compte pas ici.
    expect(stats.dossiersActifs).toBe(1);
    expect(stats.prochaineEcheance?.aideId).toBe('a1');
    expect(stats.prochaineEcheance?.projetId).toBe('p1');
    expect(stats.prochaineEcheance?.joursRestants).toBeGreaterThanOrEqual(0);
  });

  it('handles null diagnostic gracefully', () => {
    const stats = computeProjectStats(makeProjet({ id: 'p1' }), null, []);
    expect(stats.aidesIdentifiees).toBe(0);
    expect(stats.montantPotentiel).toBe(0);
    expect(stats.dossiersActifs).toBe(0);
    expect(stats.prochaineEcheance).toBeNull();
  });
});

describe('computeMonumentStats', () => {
  it('agrège les projets d’un monument, et ignore ceux des autres', () => {
    const monument = makeMonument({ id: 'm1', completionPercentage: 72 });
    const projets = [
      makeProjet({ id: 'p1', monumentId: 'm1' }),
      makeProjet({ id: 'p2', monumentId: 'm1' }),
      makeProjet({ id: 'pX', monumentId: 'm2' }), // autre monument
    ];
    const digests = {
      p1: makeDiagnostic('p1', [makeMatch(makeAide({ id: 'a1', dateLimite: NEAR_FUTURE, permanent: false }))], [], 100000),
      p2: makeDiagnostic('p2', [makeMatch(makeAide({ id: 'a2', dateLimite: FAR_FUTURE, permanent: false }))], [], 50000),
      pX: makeDiagnostic('pX', [makeMatch(makeAide({ id: 'a3', permanent: true }))], [], 999999),
    };
    const dossiers = [
      makeDossier({ id: 'd1', projetId: 'p1', monumentId: 'm1', statut: 'en_cours' }),
      makeDossier({ id: 'd2', projetId: 'p2', monumentId: 'm1', statut: 'soumis' }),
      makeDossier({ id: 'd3', projetId: 'pX', monumentId: 'm2', statut: 'en_cours' }),
    ];

    const stats = computeMonumentStats(monument, projets, digests, dossiers);

    expect(stats.projets).toBe(2);
    expect(stats.aidesIdentifiees).toBe(2);
    expect(stats.montantPotentiel).toBe(150000);
    expect(stats.dossiersActifs).toBe(1);
    expect(stats.completion).toBe(72);
    // La plus proche des échéances de ses projets.
    expect(stats.prochaineEcheance?.aideId).toBe('a1');
  });

  it('un monument sans projet rend des zéros et aucune échéance', () => {
    const stats = computeMonumentStats(makeMonument({ id: 'm1', completionPercentage: 40 }), [], {}, []);
    expect(stats.projets).toBe(0);
    expect(stats.aidesIdentifiees).toBe(0);
    expect(stats.montantPotentiel).toBe(0);
    expect(stats.prochaineEcheance).toBeNull();
    expect(stats.completion).toBe(40);
  });
});

function makeSuivi(partial: Partial<AideSuivi> & { id: string }): AideSuivi {
  return {
    id: partial.id,
    projetId: partial.projetId ?? 'p1',
    monumentId: partial.monumentId ?? 'm1',
    aideId: partial.aideId ?? 'a1',
    userId: 'u1',
    statut: partial.statut ?? 'a_faire',
    historique: [],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  } as AideSuivi;
}

describe('projectStage', () => {
  it('a 4 étapes ordonnées', () => {
    expect(PROJECT_STAGES.map((s) => s.key)).toEqual(['estimation', 'dossier', 'depot', 'suivi']);
  });

  it('rien fait → reachedIndex -1, current estimation', () => {
    const s = projectStage(null, [], []);
    expect(s.reachedIndex).toBe(-1);
    expect(s.current).toBe('estimation');
    expect(s.reached).toEqual([]);
  });

  it('diagnostic présent → étape estimation atteinte', () => {
    const diag = makeDiagnostic('p1', [], [], 0);
    const s = projectStage(diag, [], []);
    expect(s.reachedIndex).toBe(0);
    expect(s.reached).toEqual(['estimation']);
  });

  it('dossier en cours → étape dossier atteinte', () => {
    const diag = makeDiagnostic('p1', [], [], 0);
    const s = projectStage(diag, [makeDossier({ id: 'd1', monumentId: 'm1', statut: 'en_cours' })], []);
    expect(s.reachedIndex).toBe(1);
    expect(s.current).toBe('dossier');
  });

  it('dossier prêt/soumis → étape dépôt atteinte (étapes monotones)', () => {
    const s = projectStage(makeDiagnostic('p1', [], [], 0), [makeDossier({ id: 'd1', monumentId: 'm1', statut: 'soumis' })], []);
    expect(s.reachedIndex).toBe(2);
    expect(s.reached).toEqual(['estimation', 'dossier', 'depot']);
  });

  it('suivi déposé/accordé/refusé → étape suivi atteinte', () => {
    const s = projectStage(makeDiagnostic('p1', [], [], 0), [], [makeSuivi({ id: 's1', statut: 'accorde' })]);
    expect(s.reachedIndex).toBe(3);
    expect(s.current).toBe('suivi');
  });
});
