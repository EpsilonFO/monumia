import { describe, expect, it } from 'vitest';
import { projetTitre } from '@/lib/projet-titre';
import type { Projet } from '@/types';

function projet(partial: Partial<Projet>): Projet {
  return {
    id: 'p1',
    monumentId: 'm1',
    userId: 'u1',
    travauxEnvisages: null,
    questionnaire: {},
    createdAt: '',
    updatedAt: '',
    ...partial,
  };
}

describe('projetTitre', () => {
  it('utilise le titre saisi quand il y en a un', () => {
    expect(projetTitre(projet({ titre: 'Chantier du clocher' }))).toBe('Chantier du clocher');
  });

  it('ignore un titre vide ou blanc', () => {
    expect(projetTitre(projet({ titre: '   ', travauxEnvisages: ['toiture'] }))).toBe('Toiture');
  });

  it('décrit le projet par ses travaux, en clair', () => {
    expect(projetTitre(projet({ travauxEnvisages: ['toiture', 'charpente'] }))).toBe(
      'Toiture, Charpente',
    );
  });

  it('abrège au-delà de trois types de travaux', () => {
    expect(
      projetTitre(projet({ travauxEnvisages: ['toiture', 'charpente', 'couverture', 'facade'] })),
    ).toBe('Toiture, Charpente, Couverture +1');
  });

  it('retombe sur la première intention quand les travaux ne sont pas déterminés', () => {
    expect(
      projetTitre(projet({ travauxEnvisages: [], questionnaire: { _raisons: ['fiscalite'] } })),
    ).toBe('Optimiser la fiscalité');
  });

  it('rend toujours quelque chose, même sans aucune information', () => {
    expect(projetTitre(projet({}))).toBe('Projet de travaux');
  });
});

describe('projetTitre : intention appliquée au monument', () => {
  const restaurer = { _raisons: ['restauration_travaux'] };

  it("nomme le projet par l'intention et le monument, article accordé", () => {
    expect(projetTitre(projet({ questionnaire: restaurer }), 'Château de Villandry')).toBe(
      'Restaurer le Château de Villandry',
    );
    expect(projetTitre(projet({ questionnaire: restaurer }), 'Chapelle Saint-Roch')).toBe(
      'Restaurer la Chapelle Saint-Roch',
    );
    expect(
      projetTitre(projet({ questionnaire: { _raisons: ['valorisation_rayonnement'] } }), 'Abbaye de Noirlac'),
    ).toBe("Faire vivre l'Abbaye de Noirlac");
  });

  it('élide devant un h muet, pas devant un h aspiré', () => {
    expect(projetTitre(projet({ questionnaire: restaurer }), 'Hôtel de Sully')).toBe("Restaurer l'Hôtel de Sully");
    expect(projetTitre(projet({ questionnaire: restaurer }), 'Halle de Crémieu')).toBe('Restaurer la Halle de Crémieu');
  });

  it('contracte « de » avec l’article quand le verbe le demande', () => {
    const etude = { _raisons: ['etude_ingenierie'] };
    expect(projetTitre(projet({ questionnaire: etude }), 'Moulin de Daudet')).toBe(
      'Préparer les travaux du Moulin de Daudet',
    );
    expect(projetTitre(projet({ questionnaire: etude }), 'Le Clos Lucé')).toBe('Préparer les travaux du Clos Lucé');
    expect(projetTitre(projet({ questionnaire: etude }), 'Église Saint-Martin')).toBe(
      "Préparer les travaux de l'Église Saint-Martin",
    );
  });

  it("reprend l'article déjà présent dans le nom", () => {
    expect(projetTitre(projet({ questionnaire: restaurer }), 'La Commanderie')).toBe('Restaurer la Commanderie');
    expect(projetTitre(projet({ questionnaire: restaurer }), "L'Hermitage")).toBe("Restaurer l'Hermitage");
  });

  it("n'invente pas d'article devant un nom qu'on ne sait pas accorder", () => {
    expect(projetTitre(projet({ questionnaire: restaurer }), 'Notre-Dame de Bon-Secours')).toBe(
      'Restaurer Notre-Dame de Bon-Secours',
    );
  });

  it("préfère l'intention aux travaux, et le libellé seul sans le nom du monument", () => {
    const p = projet({ questionnaire: restaurer, travauxEnvisages: ['toiture'] });
    expect(projetTitre(p, 'Château de Chambord')).toBe('Restaurer le Château de Chambord');
    expect(projetTitre(p)).toBe('Restaurer ou faire des travaux');
  });

  it('garde le titre saisi', () => {
    expect(projetTitre(projet({ titre: 'Clocher', questionnaire: restaurer }), 'Église Saint-Martin')).toBe('Clocher');
  });
});
