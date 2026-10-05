import { describe, expect, it } from 'vitest';
import {
  dejaAccueilli,
  LARGEUR_BULLE,
  marquerAccueilli,
  MARGE_HALO,
  positionBulle,
} from '../bienvenue-beta';

const ecran = { largeur: 1440, hauteur: 900 };
// Le bouton Ybug tel que son script le pose : en bas à droite.
const bouton = { top: 830, left: 1340, width: 50, height: 50 };

describe('positionBulle', () => {
  it('pose la bulle au-dessus du bouton, calée sur son bord droit', () => {
    const p = positionBulle(bouton, ecran);
    expect(p.largeur).toBe(LARGEUR_BULLE);
    expect(p.left + p.largeur).toBe(bouton.left + bouton.width + MARGE_HALO);
    // Le bas de la bulle reste au-dessus du halo.
    expect(ecran.hauteur - p.bottom).toBeLessThan(bouton.top - MARGE_HALO);
  });

  it('ne sort jamais de l’écran, et la pointe vise toujours le bouton', () => {
    const telephone = { largeur: 360, hauteur: 740 };
    const b = { top: 600, left: 300, width: 50, height: 50 };
    const p = positionBulle(b, telephone);
    expect(p.left).toBeGreaterThanOrEqual(16);
    expect(p.left + p.largeur).toBeLessThanOrEqual(telephone.largeur - 16);
    expect(p.left + p.pointe).toBeGreaterThan(b.left);
    expect(p.left + p.pointe).toBeLessThan(b.left + b.width + MARGE_HALO);
  });
});

describe('accueil une fois par compte', () => {
  // Pas de localStorage sous l'environnement `node` : c'est le repli en
  // mémoire qui tient, comme dans un navigateur au stockage bloqué.
  it('retient le compte accueilli, et lui seul', () => {
    expect(dejaAccueilli('a')).toBe(false);
    marquerAccueilli('a');
    expect(dejaAccueilli('a')).toBe(true);
    expect(dejaAccueilli('b')).toBe(false);
  });
});
