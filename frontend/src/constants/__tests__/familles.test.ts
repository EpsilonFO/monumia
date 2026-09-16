import { describe, it, expect } from 'vitest';
import type { ProjectQuestionnaireAnswers } from '@/types';
import {
  FAMILLE_OPTIONS,
  FAMILLE_TRAVAUX,
  FAMILLES_CHOIX,
  FAMILLES_KEY,
  familleProposee,
  libelleFamille,
  readFamilles,
} from '../familles';

/**
 * Miroir de `backend/tests/test_familles.py::TableDesFamillesTest`.
 *
 * Les deux tables doivent dire la même chose : une famille côté front qu'aucun
 * code backend n'accepte est un filtre qui ne filtre rien (fail-open), et une
 * famille backend sans libellé s'afficherait sous son code technique. Ces
 * assertions figent donc exactement les mêmes valeurs que le test Python.
 */
describe('table des familles', () => {
  it('porte les treize familles et leurs libellés', () => {
    expect(FAMILLE_OPTIONS.map((o) => [o.value, o.label])).toEqual([
      ['restauration_bati', 'Restauration du bâti'],
      ['energie_climat', 'Énergie et climat'],
      ['eau_nature_domaine', 'Eau, nature et domaine'],
      ['securite_risques', 'Sécurité et risques'],
      ['parcs_jardins_paysages', 'Parcs, jardins et paysages'],
      ['tourisme_hebergement', 'Tourisme et hébergement'],
      ['activite_economique_lieu', 'Activité économique dans le lieu'],
      ['spectacles_manifestations', 'Spectacles et manifestations'],
      ['vie_locale_associative', 'Vie locale et associative'],
      ['mediation_numerique_expositions', 'Médiation, expositions, musée, numérique'],
      ['accessibilite_publics', 'Accessibilité et accueil des publics'],
      ['etudes_ingenierie', 'Études et ingénierie'],
      ['labels_passerelles', 'Labels et passerelles'],
    ]);
  });

  it('donne un indice à chaque famille', () => {
    for (const option of FAMILLE_OPTIONS) {
      expect(option.hint.trim().length, option.value).toBeGreaterThan(0);
    }
  });

  /**
   * L'étape ne propose pas les treize : les cinq familles de chantier et les
   * études relèvent des intentions « Restaurer » et « Préparer le projet », que
   * le moteur implique déjà (`FAMILLES_PAR_RAISON`) sans rien demander.
   * `parcs_jardins_paysages` fait exception — ouvrir un jardin à la visite est
   * un projet de « faire vivre » à part entière.
   */
  it('ne propose que les familles d’un projet « faire vivre »', () => {
    expect(FAMILLES_CHOIX).toEqual([
      'spectacles_manifestations',
      'mediation_numerique_expositions',
      'tourisme_hebergement',
      'vie_locale_associative',
      'labels_passerelles',
      'parcs_jardins_paysages',
      'accessibilite_publics',
      'activite_economique_lieu',
    ]);
    // Toutes proposées existent, et la tuile des travaux aussi.
    const codes = FAMILLE_OPTIONS.map((o) => o.value);
    for (const famille of [...FAMILLES_CHOIX, FAMILLE_TRAVAUX]) {
      expect(codes, famille).toContain(famille);
    }
    // La famille de la tuile « Des travaux sont nécessaires » n'est PAS dans
    // les tuiles ordinaires : elle a son propre rendu, et rouvre une étape.
    expect(FAMILLES_CHOIX).not.toContain(FAMILLE_TRAVAUX);
  });

  it('dit si une famille est encore proposée', () => {
    expect(familleProposee('spectacles_manifestations')).toBe(true);
    expect(familleProposee('etudes_ingenierie')).toBe(false);
    expect(familleProposee('inventee')).toBe(false);
  });

  it('rend le libellé, ou le code d’une famille inconnue', () => {
    expect(libelleFamille('tourisme_hebergement')).toBe('Tourisme et hébergement');
    // Fail-open : une famille venue du serveur et inconnue ici s'affiche telle
    // quelle plutôt que de vider la puce.
    expect(libelleFamille('famille_future')).toBe('famille_future');
  });
});

/**
 * Le TRI-ÉTAT est le point délicat : `null` (« la question n'a pas été posée »)
 * et `[]` (« montrez-moi tout ») ne filtrent ni l'un ni l'autre, mais seul le
 * second est une réponse — et c'est ce qui permet de ne pas reposer la question.
 */
describe('readFamilles', () => {
  it('rend null quand la clé est absente', () => {
    expect(readFamilles(undefined)).toBeNull();
    expect(readFamilles({})).toBeNull();
    expect(readFamilles({ etat_travaux: 'aucun' })).toBeNull();
  });

  it('distingue « montrez-moi tout » d’une question non posée', () => {
    expect(readFamilles({ [FAMILLES_KEY]: [] })).toEqual([]);
  });

  it('rend les familles cochées', () => {
    expect(readFamilles({ [FAMILLES_KEY]: ['spectacles_manifestations'] })).toEqual([
      'spectacles_manifestations',
    ]);
  });

  it('ignore une valeur mal formée', () => {
    // Le questionnaire vient de la base : il peut précéder la clé ou l'avoir
    // mal écrite. On rend `null` (question à reposer) plutôt qu'un filtre faux.
    // Le cast est le sujet du test : ces valeurs sortent de la base, pas du
    // type `ProjectQuestionnaireAnswers` que le wizard respecte.
    const malForme = (valeur: unknown) =>
      readFamilles({ [FAMILLES_KEY]: valeur } as ProjectQuestionnaireAnswers);
    expect(malForme('spectacles_manifestations')).toBeNull();
    expect(malForme(42)).toBeNull();
  });

  it('écarte les éléments non textuels d’une liste', () => {
    expect(
      readFamilles({
        [FAMILLES_KEY]: ['spectacles_manifestations', 7],
      } as unknown as ProjectQuestionnaireAnswers),
    ).toEqual(['spectacles_manifestations']);
  });
});
