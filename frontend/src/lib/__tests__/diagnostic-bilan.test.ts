import { describe, expect, it } from 'vitest';
import {
  bilanDiagnostic,
  bilanInvite,
  matchPourAide,
  minutesPourQuestions,
  questionsPourAide,
} from '../diagnostic-bilan';
import type { Aide, AideDiagnosticResult, AideMatchResult, QcmQuestion } from '@/types';

/** Aide réduite à ce que le bilan lit. */
function aide(id: string): Aide {
  return { id, nom: id, nomCourt: id } as unknown as Aide;
}

function match(id: string, over: Partial<AideMatchResult> = {}): AideMatchResult {
  return {
    aide: aide(id),
    eligible: false,
    criteresRemplis: [],
    criteresNonRemplis: [],
    ...over,
  };
}

function question(id: string, aideIds: string[], over: Partial<QcmQuestion> = {}): QcmQuestion {
  return {
    id,
    question: id,
    options: [
      { id: 'oui', label: 'Oui' },
      { id: 'non', label: 'Non' },
      { id: 'je_ne_sais_pas', label: 'Je ne sais pas', unknown: true },
    ],
    aideIds,
    eliminatingOptionIds: [],
    ...over,
  };
}

describe('minutesPourQuestions', () => {
  it('vingt secondes par question, arrondi aux cinq minutes, plancher à cinq', () => {
    expect(minutesPourQuestions(0)).toBe(0);
    expect(minutesPourQuestions(1)).toBe(5);
    expect(minutesPourQuestions(16)).toBe(5);
    expect(minutesPourQuestions(31)).toBe(10);
    expect(minutesPourQuestions(60)).toBe(20);
  });
});

describe('questionsPourAide', () => {
  it('se fonde sur aideIds, pas sur la catégorie', () => {
    // Condition bloquée par une passerelle `applies_if` : le moteur ne pose pas
    // de `categorie` sur son évaluation quand son propre fait est connu. Seul
    // `aideIds` rattache alors la question à l'aide.
    const q = question('projet_hebergement_touristique', ['gite-x']);
    expect(questionsPourAide('gite-x', [q], {}).map((x) => x.id)).toEqual([
      'projet_hebergement_touristique',
    ]);
    expect(questionsPourAide('autre-aide', [q], {})).toEqual([]);
  });

  it('une réponse « je ne sais pas » laisse la question à poser', () => {
    const q = question('etat_travaux', ['a']);
    expect(questionsPourAide('a', [q], { etat_travaux: 'je_ne_sais_pas' })).toHaveLength(1);
    expect(questionsPourAide('a', [q], { etat_travaux: 'skip' })).toHaveLength(1);
    expect(questionsPourAide('a', [q], { etat_travaux: 'oui' })).toHaveLength(0);
  });

  it('choix multiple : une seule vraie réponse suffit à résoudre', () => {
    const q = question('travaux', ['a'], { multiple: true });
    expect(questionsPourAide('a', [q], { travaux: ['je_ne_sais_pas'] })).toHaveLength(1);
    expect(questionsPourAide('a', [q], { travaux: ['je_ne_sais_pas', 'oui'] })).toHaveLength(0);
  });

  it('garde l’ordre du moteur (porteuses d’abord)', () => {
    const porteuse = question('ouverture_public', ['a']);
    const dependante = question('jours_ouverture_public_par_an', ['a'], {
      dependsOn: { questionId: 'ouverture_public', showForOptionIds: ['oui'] },
    });
    expect(questionsPourAide('a', [porteuse, dependante], {}).map((q) => q.id)).toEqual([
      'ouverture_public',
      'jours_ouverture_public_par_an',
    ]);
  });
});

describe('bilanDiagnostic', () => {
  const result: AideDiagnosticResult = {
    monumentId: 'm1',
    timestamp: '2026-09-16T00:00:00Z',
    totalAidesAnalysees: 120,
    aidesEligibles: [match('ok-1'), match('ok-2', { eligible: true })],
    aidesPotentiellementEligibles: [match('conf-1'), match('conf-2'), match('conf-3')],
    aidesAtteignables: [match('debloc-1')],
    aidesNonEligibles: [
      match('refus-reponse', { elimineParReponse: true }),
      match('refus-filtre', { elimineParReponse: false }),
      match('refus-filtre-2'),
    ],
    qcmQuestions: [
      question('q-conf-1', ['conf-1']),
      question('q-conf-2a', ['conf-2']),
      question('q-conf-2b', ['conf-2']),
      question('q-conf-3', ['conf-3']),
    ],
  };

  it('sépare ce que les réponses ont écarté de ce qui est à portée', () => {
    const bilan = bilanDiagnostic(result);
    expect(bilan.aPortee).toBe(120);
    expect(bilan.eligibles).toBe(2);
    expect(bilan.atteignables).toBe(1);
    expect(bilan.aConfirmer).toBe(3);
    // Les deux refus venus des seuls filtres automatiques n'y entrent pas :
    // l'utilisateur n'y est pour rien, les lui compter serait un mensonge.
    expect(bilan.ecarteesParReponses).toBe(1);
  });

  it('compte les aides qu’une SEULE question sépare d’un verdict', () => {
    // conf-1 et conf-3 en ont une chacune, conf-2 en a deux.
    expect(bilanDiagnostic(result).aConfirmerUneQuestion).toBe(2);
  });

  it('les questions déjà répondues ne comptent plus dans les restantes', () => {
    const bilan = bilanDiagnostic({ ...result, qcmAnswers: { 'q-conf-1': 'oui' } });
    expect(bilan.aConfirmerUneQuestion).toBe(1);
    // `questionsRestantes` reste le jeu rendu par le moteur : ce sont les faits
    // encore inconnus après la relance.
    expect(bilan.questionsRestantes).toBe(4);
  });

  it('un résultat sans questions donne un bilan à zéro minute', () => {
    const bilan = bilanDiagnostic({ ...result, qcmQuestions: [] });
    expect(bilan.questionsRestantes).toBe(0);
    expect(bilan.minutesEstimees).toBe(0);
  });
});

describe('bilanInvite', () => {
  it('ne rend que ce que le parcours invité sait : des questions et une durée', () => {
    expect(
      bilanInvite({
        qcmQuestions: [question('a', ['a1']), question('b', ['a2'])],
        synthese: {
          eligibles: 1,
          potentielles: 2,
          atteignables: 0,
          totalAnalysees: 40,
        },
      }),
    ).toEqual({ questionsRestantes: 2, minutesEstimees: 5 });
  });
});

describe('matchPourAide', () => {
  const diagnostic = (over: Partial<AideDiagnosticResult> = {}): AideDiagnosticResult => ({
    monumentId: 'm',
    timestamp: '',
    totalAidesAnalysees: 1,
    aidesEligibles: [],
    aidesPotentiellementEligibles: [],
    aidesNonEligibles: [],
    ...over,
  });

  it('rend le verdict du moteur quand l’aide est dans un seau', () => {
    const m = match('ilots', { statut: 'potentiel', eligible: true });
    expect(matchPourAide(diagnostic({ aidesPotentiellementEligibles: [m] }), aide('ilots'), 'ilots')).toBe(m);
  });

  it('une aide écartée par sa question de périmètre est un refus dû à la réponse', () => {
    const d = diagnostic({ aidesHorsPerimetre: { ilots: 'Votre projet porte-t-il sur la végétalisation ?' } });
    const m = matchPourAide(d, aide('ilots'), 'ilots');
    expect(m?.statut).toBe('non_eligible');
    expect(m?.elimineParReponse).toBe(true);
    expect(m?.criteresNonRemplis[0]).toContain('Votre projet porte-t-il sur la végétalisation ?');
  });

  it('sans l’aide chargée, ou absente de partout, pas de verdict', () => {
    const d = diagnostic({ aidesHorsPerimetre: { ilots: 'Q ?' } });
    expect(matchPourAide(d, null, 'ilots')).toBeNull();
    expect(matchPourAide(d, aide('autre'), 'ilots')).toBeNull();
    expect(matchPourAide(diagnostic(), aide('ilots'), 'ilots')).toBeNull();
  });
});
