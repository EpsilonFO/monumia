import { describe, expect, it } from 'vitest';
import { FENETRE_MS, rechargementRecent } from '@/lib/morceau-perdu';

/** Un stockage figé sur une valeur, comme `sessionStorage` après un essai. */
function stockage(valeur: string | null) {
  return { getItem: () => valeur };
}

describe('rechargementRecent', () => {
  const maintenant = 1_000_000;

  it("faux sans essai mémorisé : le premier morceau perdu recharge", () => {
    expect(rechargementRecent(maintenant, stockage(null))).toBe(false);
  });

  it('vrai juste après un essai : pas de boucle de rechargements', () => {
    expect(rechargementRecent(maintenant, stockage(String(maintenant - 1_000)))).toBe(true);
  });

  it("faux une fois la fenêtre passée : un déploiement suivant recharge encore", () => {
    expect(rechargementRecent(maintenant, stockage(String(maintenant - FENETRE_MS - 1)))).toBe(false);
  });

  it('faux sur une valeur illisible', () => {
    expect(rechargementRecent(maintenant, stockage('pas un nombre'))).toBe(false);
  });
});
