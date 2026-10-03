import { describe, expect, it } from 'vitest';
import { aFaireMaintenant, quandLibelle } from '@/lib/a-faire-maintenant';
import type { ProjectDeadline } from '@/lib/project-stats';
import type { Dossier, Monument, ProjectDigest } from '@/types';

const monuments = [{ id: 'm1', nom: 'Église de la Nativité' }] as Monument[];

const echeanceAide = (aideId: string, joursRestants = 36): ProjectDeadline => ({
  id: `aide-${aideId}`,
  label: 'Nom administratif',
  date: '2026-10-31',
  source: 'aide',
  joursRestants,
  urgency: 'normal',
  projetId: 'p1',
  monumentId: 'm1',
  aideId,
});

const digest: ProjectDigest = {
  projetId: 'p1',
  monumentId: 'm1',
  aidesEligibles: [{ aide: { id: 'ok', nom: 'Aide ok', categorie: 'region', permanent: false } }],
  aidesPotentiellementEligibles: [
    {
      aide: {
        id: 'q',
        nom: 'Appel à projets France Bois Forêt',
        categorie: 'fondation',
        permanent: false,
        carte: { titre: 'Dotation France Bois Forêt', chapeau: 'Pour une restauration en bois.', montant: { valeur: "Jusqu'à 10 000 €" } },
      },
      questionsRestantes: 3,
    },
    { aide: { id: 'v', nom: 'Aide à vérifier', categorie: 'region', permanent: false }, questionsRestantes: 0 },
  ],
  aidesAtteignables: [{ aide: { id: 'd', nom: 'Aide à débloquer', categorie: 'region', permanent: false, montantMax: 5000 } }],
};

describe('aFaireMaintenant', () => {
  it("ne met rien en avant sans date", () => {
    expect(aFaireMaintenant([], { p1: digest }, [], monuments)).toBeNull();
  });

  it('rédige une aide à confirmer comme sa carte, avec ses questions', () => {
    const a = aFaireMaintenant([echeanceAide('q')], { p1: digest }, [], monuments)!;
    expect(a.nature).toBe('questions');
    expect(a.questions).toBe(3);
    expect(a.titre).toBe('Dotation France Bois Forêt');
    expect(a.montant).toBe("Jusqu'à 10 000 €");
    expect(a.detail).toBe('Pour une restauration en bois.');
    expect(a.monumentNom).toBe('Église de la Nativité');
  });

  it('distingue éligible, à vérifier et démarche', () => {
    const nature = (id: string) => aFaireMaintenant([echeanceAide(id)], { p1: digest }, [], monuments)!.nature;
    expect(nature('ok')).toBe('eligible');
    expect(nature('v')).toBe('verifier');
    expect(nature('d')).toBe('demarche');
  });

  it("retombe sur le montant maximal quand la carte n'en écrit pas", () => {
    const a = aFaireMaintenant([echeanceAide('d')], { p1: digest }, [], monuments)!;
    expect(a.montant).toMatch(/^Jusqu'à 5\s000\s€$/);
  });

  it("titre une échéance de dossier par le dossier, et garde son intitulé", () => {
    const echeance: ProjectDeadline = {
      id: 'dossier-d1-e1',
      label: 'Envoyer le devis',
      date: '2026-10-01',
      source: 'dossier',
      joursRestants: -2,
      urgency: 'past',
      projetId: 'p1',
      monumentId: 'm1',
      dossierId: 'd1',
    };
    const dossiers = [{ id: 'd1', titre: 'Subvention DRAC' }] as Dossier[];
    const a = aFaireMaintenant([echeance], { p1: digest }, dossiers, monuments)!;
    expect(a.nature).toBe('dossier');
    expect(a.titre).toBe('Subvention DRAC');
    expect(a.detail).toBe('Envoyer le devis');
  });
});

describe('quandLibelle', () => {
  it('dit le délai comme une personne', () => {
    expect(quandLibelle(36)).toBe('dans 36 jours');
    expect(quandLibelle(1)).toBe('demain');
    expect(quandLibelle(0)).toBe("aujourd'hui");
    expect(quandLibelle(-1)).toBe('en retard de 1 jour');
    expect(quandLibelle(-3)).toBe('en retard de 3 jours');
  });
});
