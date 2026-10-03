import { describe, it, expect } from 'vitest';
import {
  OFFRE_GRATUITE,
  OFFRE_MULTI_MONUMENTS,
  OFFRE_VEILLE,
  PLANS_VENDABLES,
  libelleMonuments,
  offrePour,
  sousLePlafond,
} from '../offres';

/**
 * Miroir de `backend/tests/test_billing_access.py::TableDesOffresTest`.
 *
 * Les deux tables doivent dire la même chose : un bouton affiché que le serveur
 * refuse est le pire des deux mondes — l'utilisateur clique, échoue, et croit
 * que le produit est cassé. Ces assertions figent donc exactement les mêmes
 * valeurs que celles du test Python.
 */
describe('table des offres', () => {
  it('gratuit : un monument, deux projets, et rien du calendrier', () => {
    expect(OFFRE_GRATUITE).toEqual({
      nom: 'Gratuit',
      monumentsMax: 1,
      projetsMax: 2,
      dashboard: false,
      equipe: false,
      suppressionMonument: false,
      suppressionProjet: false,
      aidesBientot: false,
      echeancier: false,
      rappelsEmail: false,
    });
  });

  it('veille : le calendrier, l’équipe et les projets, pas les monuments', () => {
    expect(OFFRE_VEILLE.projetsMax).toBeNull();
    expect(OFFRE_VEILLE.equipe).toBe(true);
    expect(OFFRE_VEILLE.suppressionProjet).toBe(true);
    expect(OFFRE_VEILLE.aidesBientot).toBe(true);
    expect(OFFRE_VEILLE.echeancier).toBe(true);
    expect(OFFRE_VEILLE.rappelsEmail).toBe(true);
    // Ce que Veille ne donne PAS.
    expect(OFFRE_VEILLE.monumentsMax).toBe(1);
    expect(OFFRE_VEILLE.suppressionMonument).toBe(false);
    expect(OFFRE_VEILLE.dashboard).toBe(false);
  });

  it('multi-monuments contient veille', () => {
    expect(OFFRE_MULTI_MONUMENTS.monumentsMax).toBeNull();
    expect(OFFRE_MULTI_MONUMENTS.projetsMax).toBeNull();
    expect(OFFRE_MULTI_MONUMENTS.dashboard).toBe(true);
    expect(OFFRE_MULTI_MONUMENTS.equipe).toBe(true);
    expect(OFFRE_MULTI_MONUMENTS.suppressionMonument).toBe(true);
    expect(OFFRE_MULTI_MONUMENTS.aidesBientot).toBe(true);
    expect(OFFRE_MULTI_MONUMENTS.echeancier).toBe(true);
    expect(OFFRE_MULTI_MONUMENTS.rappelsEmail).toBe(true);
  });
});

describe('offrePour', () => {
  it('aucun plan = offre gratuite', () => {
    expect(offrePour([])).toEqual(OFFRE_GRATUITE);
    expect(offrePour(undefined)).toEqual(OFFRE_GRATUITE);
    expect(offrePour(null)).toEqual(OFFRE_GRATUITE);
  });

  it('un plan connu rend son offre', () => {
    expect(offrePour(['veille'])).toEqual(OFFRE_VEILLE);
    expect(offrePour(['multi_monuments'])).toEqual(OFFRE_MULTI_MONUMENTS);
  });

  it('un plan inconnu n’ouvre rien', () => {
    // Abonnement antérieur aux trois offres : l'accès legacy a été coupé.
    expect(offrePour(['abonnement'])).toEqual(OFFRE_GRATUITE);
    expect(offrePour(['dossier', 'abonnement'])).toEqual(OFFRE_GRATUITE);
  });

  it('cumuler ne retire rien', () => {
    // Arrive le temps d'une montée en gamme, les deux abonnements actifs.
    expect(offrePour(['veille', 'multi_monuments'])).toEqual(OFFRE_MULTI_MONUMENTS);
  });

  it('un plan inconnu à côté d’un plan connu ne dégrade pas l’offre', () => {
    expect(offrePour(['veille', 'offre-pirate'])).toEqual(OFFRE_VEILLE);
  });
});

describe('sousLePlafond', () => {
  it('null vaut illimité', () => {
    expect(sousLePlafond(null, 0)).toBe(true);
    expect(sousLePlafond(null, 900)).toBe(true);
  });

  it('compare strictement au plafond', () => {
    expect(sousLePlafond(1, 0)).toBe(true);
    expect(sousLePlafond(1, 1)).toBe(false);
    expect(sousLePlafond(2, 1)).toBe(true);
    expect(sousLePlafond(2, 2)).toBe(false);
    expect(sousLePlafond(2, 5)).toBe(false);
  });
});

describe('libelleMonuments', () => {
  it('singulier tant que l’offre plafonne à un bien', () => {
    expect(libelleMonuments(OFFRE_GRATUITE)).toBe('Mon monument');
    expect(libelleMonuments(OFFRE_VEILLE)).toBe('Mon monument');
  });

  it('pluriel dès que le plafond saute', () => {
    // Le plafond décide, pas le nombre de monuments réellement enregistrés.
    expect(libelleMonuments(OFFRE_MULTI_MONUMENTS)).toBe('Mes monuments');
  });
});

describe('canal de vente', () => {
  it('aucune offre ne s’achète en libre-service', () => {
    // Les deux se négocient : la page Tarifs n'affiche aucun montant et mène à
    // un courrier, et le serveur refuse la session Checkout (409). Ce test
    // garde les deux côtés d'accord — un bouton d'achat qui promettrait ce que
    // le serveur refuse est le pire des deux mondes.
    expect(PLANS_VENDABLES).toEqual([]);
  });
});
