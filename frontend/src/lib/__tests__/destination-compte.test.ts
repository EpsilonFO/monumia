import { describe, it, expect } from 'vitest';
import { destinationCompte } from '../destination-compte';
import { OFFRE_GRATUITE, OFFRE_MULTI_MONUMENTS, OFFRE_VEILLE } from '../offres';

/**
 * Où mène « Mon compte » depuis la landing (route `/mon-compte`).
 *
 * Le test vaut surtout pour ce qu'il interdit : envoyer sur le tableau de bord
 * quelqu'un qui le verrait flouté, et envoyer enregistrer un monument
 * quelqu'un qui en a déjà un. Les deux se vérifieraient à la main en changeant
 * d'offre et de compte ; ici c'est une fonction pure.
 */
describe('destination du compte', () => {
  it('Multi-monuments : le tableau de bord, même sans aucun monument', () => {
    expect(
      destinationCompte({ offre: OFFRE_MULTI_MONUMENTS, monumentIds: [] }),
    ).toBe('/app');
    expect(
      destinationCompte({ offre: OFFRE_MULTI_MONUMENTS, monumentIds: ['m1', 'm2'] }),
    ).toBe('/app');
  });

  it('sans le tableau de bord, un seul monument : sa fiche', () => {
    expect(destinationCompte({ offre: OFFRE_GRATUITE, monumentIds: ['m1'] })).toBe(
      '/app/monuments/m1',
    );
    expect(destinationCompte({ offre: OFFRE_VEILLE, monumentIds: ['m1'] })).toBe(
      '/app/monuments/m1',
    );
  });

  it('sans le tableau de bord, plusieurs monuments : la liste, pas un choix arbitraire', () => {
    expect(
      destinationCompte({ offre: OFFRE_VEILLE, monumentIds: ['m1', 'm2'] }),
    ).toBe('/app/monuments');
  });

  it('aucun monument : le wizard d’enregistrement', () => {
    expect(destinationCompte({ offre: OFFRE_GRATUITE, monumentIds: [] })).toBe(
      '/app/monuments/nouveau',
    );
  });

  it('un collaborateur sans monument va à la liste, jamais au wizard', () => {
    // Son compte n'est pas fait pour enregistrer un bien : un partage retiré
    // doit se constater, pas se transformer en invitation à créer.
    expect(
      destinationCompte({
        offre: OFFRE_GRATUITE,
        monumentIds: [],
        accountType: 'collaborateur',
      }),
    ).toBe('/app/monuments');
  });

  it('le tableau de bord passe avant tout le reste, collaborateur compris', () => {
    expect(
      destinationCompte({
        offre: OFFRE_MULTI_MONUMENTS,
        monumentIds: ['m1'],
        accountType: 'collaborateur',
      }),
    ).toBe('/app');
  });
});
