import { describe, expect, it } from 'vitest';
import {
  chapeauAide,
  dateLongue,
  etapesAide,
  etapesDeLaDemarche,
  financeurAide,
  guichet,
  lierContacts,
  montantAide,
  piecesAide,
  reglementDe,
  titreAide,
} from '../fiche-aide';
import type { Aide, AideConditionReglement, Dossier } from '@/types';

const JOUR = new Date(2026, 8, 23); // 23 septembre 2026

const aide = (over: Partial<Aide> = {}): Aide =>
  ({
    id: 'drac-mh-classes',
    nom: 'Subvention DRAC pour travaux sur immeuble classé au titre des monuments historiques',
    nomCourt: 'Subvention DRAC (immeuble classé)',
    description: "Subvention de l'État.",
    descriptionLongue: '',
    categorie: 'etat_drac',
    type: 'subvention',
    organisme: 'DRAC',
    criteres: {},
    demarcheDescription: '',
    documentsRequis: [],
    delaiInstruction: '',
    permanent: true,
    baseTTC: false,
    ...over,
  }) as Aide;

const condition = (over: Partial<AideConditionReglement>): AideConditionReglement => ({
  id: 'c',
  text: 'Texte.',
  quote: null,
  kind: 'info',
  effect: 'info',
  derogationPossible: false,
  ...over,
});

describe('dateLongue', () => {
  it('écrit le premier du mois « 1er »', () => {
    expect(dateLongue('2026-06-01')).toBe('1er juin 2026');
    expect(dateLongue('2026-08-31')).toBe('31 août 2026');
  });
});

describe('guichet', () => {
  it("permanent : ouvert toute l'année", () => {
    expect(guichet(aide(), JOUR)).toMatchObject({ etat: 'ouvert', libelle: "Ouvert toute l'année" });
  });

  it('date limite passée : clos, avec son bandeau', () => {
    const g = guichet(aide({ permanent: false, dateLimite: '2026-08-31' }), JOUR);
    expect(g.etat).toBe('clos');
    expect(g.libelle).toBe('Clos depuis le 31 août 2026');
    expect(g.valeur).toBe('Date limite passée : 31 août 2026');
    expect(g.bandeau?.titre).toBe('Clos depuis le 31 août 2026');
  });

  it('une date limite du jour reste ouverte, comme dans le moteur', () => {
    expect(guichet(aide({ permanent: false, dateLimite: '2026-09-23' }), JOUR).etat).toBe('ouvert');
  });

  it('ouverture future : bientôt, avec la fenêtre complète', () => {
    const g = guichet(aide({ permanent: false, dateOuverture: '2026-10-01', dateLimite: '2026-12-15' }), JOUR);
    expect(g.etat).toBe('bientot');
    expect(g.valeur).toBe('Du 1er octobre 2026 au 15 décembre 2026');
  });

  it("sans aucune date : à confirmer, jamais clos (fail-open)", () => {
    const g = guichet(aide({ permanent: false }), JOUR);
    expect(g.etat).toBe('attente');
    expect(g.libelle).toBe('Dates à confirmer');
  });
});

describe("identité de l'aide", () => {
  it('préfère la fiche rédigée aux champs bruts', () => {
    const a = aide({
      carte: { titre: 'Subvention DRAC pour un immeuble classé', financeur: 'DRAC · ministère de la Culture', chapeau: 'Chapeau.' },
    });
    expect(titreAide(a)).toBe('Subvention DRAC pour un immeuble classé');
    expect(financeurAide(a)).toBe('DRAC · ministère de la Culture');
    expect(chapeauAide(a)).toBe('Chapeau.');
  });

  it('retombe sur le nom court, l’organisme et la description', () => {
    expect(titreAide(aide())).toBe('Subvention DRAC (immeuble classé)');
    expect(financeurAide(aide())).toBe('DRAC');
    expect(chapeauAide(aide())).toBe("Subvention de l'État.");
  });

  it('une aide à venir caviardée affiche sa catégorie à la place du financeur', () => {
    expect(financeurAide(aide({ organisme: '', carte: { financeur: null } }))).toBe('État (DRAC)');
  });

  it('montant : le rédigé, sinon le taux, sinon le plafond', () => {
    expect(montantAide(aide({ carte: { montant: { valeur: '40 % en moyenne' } } }))?.valeur).toBe('40 % en moyenne');
    expect(montantAide(aide({ tauxMax: 40 }))?.valeur).toBe("Jusqu'à 40 %");
    expect(montantAide(aide({ montantMax: 35000 }))?.valeur).toMatch(/^Jusqu'à 35\s000\s€$/);
    expect(montantAide(aide())).toBeNull();
  });
});

describe('reglementDe', () => {
  const reglement = [
    condition({ id: 'taux', text: 'Le taux est de 40 %.', kind: 'info' }),
    condition({ id: 'non-commences', text: 'Ne pas commencer.', kind: 'user_fact', effect: 'gate' }),
    condition({ id: 'modulation', text: 'Taux modulé.', kind: 'discretionary', effect: 'modulateur' }),
    condition({ id: 'apport', text: 'Apport de 20 %.', kind: 'manual_check' }),
  ];

  it("les gates d'abord, puis les rubriques ; la numérotation suit l'affichage", () => {
    const r = reglementDe({
      reglement,
      fiche: {
        essentiel: {},
        conseils: [],
        etapes: [],
        points: {
          taux: { titre: '40 %', theme: 'montant' },
          apport: { titre: 'Apport', theme: 'candidater' },
          modulation: { titre: 'Modulation', theme: 'montant' },
        },
      },
    });
    expect(r.conditions.map((p) => [p.id, p.n])).toEqual([['non-commences', 1]]);
    expect(r.rubriques.map((x) => x.cle)).toEqual(['candidater', 'montant']);
    expect(r.rubriques[1].points.map((p) => [p.id, p.n])).toEqual([['taux', 3], ['modulation', 4]]);
    expect(r.total).toBe(4);
  });

  it('pastilles : à vérifier (manual_check), au choix du financeur (discretionary)', () => {
    const r = reglementDe({ reglement, fiche: null });
    const tous = [...r.conditions, ...r.rubriques.flatMap((x) => x.points)];
    const pastille = (id: string) => tous.find((p) => p.id === id)?.pastille;
    expect(pastille('apport')).toBe('verifier');
    expect(pastille('modulation')).toBe('choix');
    expect(pastille('non-commences')).toBeNull();
  });

  it('sans fiche : titre tiré du texte, rubriques de repli', () => {
    const r = reglementDe({ reglement, fiche: null });
    expect(r.rubriques.map((x) => x.cle)).toEqual(['montant', 'autres']);
    expect(r.conditions[0].titre).toBe('Ne pas commencer');
    expect(r.conditions[0].resume).toBe('Ne pas commencer.');
  });

  it('la recherche ignore accents et casse', () => {
    const r = reglementDe({ reglement: [condition({ id: 'x', text: 'Dépenses ÉLIGIBLES.' })], fiche: null });
    expect(r.rubriques[0].points[0].cherche).toContain('depenses eligibles');
  });
});

describe('étapes', () => {
  it('découpe une démarche numérotée d’un seul tenant', () => {
    expect(etapesDeLaDemarche('Avant tout : appeler. 1. Consulter la DRAC. 2. Déposer 4 000 € de devis. 3. Attendre.')).toEqual([
      'Avant tout : appeler.',
      'Consulter la DRAC.',
      'Déposer 4 000 € de devis.',
      'Attendre.',
    ]);
  });

  it('un nombre suivi d’un point juste avant l’étape ne la masque pas', () => {
    expect(etapesDeLaDemarche('1. Appeler le 01 64 14 73 18. 2. Déposer en ligne. 3. Attendre.')).toEqual([
      'Appeler le 01 64 14 73 18.',
      'Déposer en ligne.',
      'Attendre.',
    ]);
  });

  it('préfère les étapes rédigées', () => {
    const fiche = { essentiel: {}, conseils: [], etapes: [{ titre: 'Déposez en ligne' }], points: {} };
    expect(etapesAide({ fiche, demarcheDescription: '1. A. 2. B.' })).toEqual([{ titre: 'Déposez en ligne' }]);
  });
});

describe('piecesAide', () => {
  const docs = [
    { nom: 'RIB' },
    { nom: 'Cerfa', url: 'https://ex.fr/cerfa' },
    { nom: 'Déclaration préalable', obligatoire: false, note: 'Selon le cas.' },
  ];

  it("sans dossier, la liste de l'aide, toutes les cases vides", () => {
    const p = piecesAide({ documentsRequis: docs });
    expect(p.map((x) => [x.nom, x.obligatoire, x.deposee])).toEqual([
      ['RIB', true, false],
      ['Cerfa', true, false],
      ['Déclaration préalable', false, false],
    ]);
  });

  it('affiche le libellé rédigé, sans changer la clé de la pièce', () => {
    const fiche = { essentiel: {}, conseils: [], etapes: [], points: {}, pieces: { RIB: 'Relevé d’identité bancaire' } };
    const p = piecesAide({ documentsRequis: docs, fiche });
    expect(p[0].nom).toBe('Relevé d’identité bancaire');
    expect(p[0].cle).toBe('0-RIB');
  });

  it('avec un dossier, sa checklist fait foi', () => {
    const dossier = {
      checklist: [
        { id: 'b', label: 'Cerfa', description: '', statut: 'manquant', obligatoire: true, categorie: 'document', ordre: 2 },
        { id: 'a', label: 'RIB', description: '', statut: 'fourni', obligatoire: true, categorie: 'document', ordre: 1 },
      ],
    } as unknown as Dossier;
    const p = piecesAide({ documentsRequis: docs }, dossier);
    expect(p.map((x) => [x.nom, x.deposee, x.url])).toEqual([
      ['RIB', true, undefined],
      ['Cerfa', false, 'https://ex.fr/cerfa'],
    ]);
  });
});

describe('lierContacts', () => {
  it('rend cliquables un email et un téléphone', () => {
    expect(lierContacts('Écrire à a.b@culture.gouv.fr ou au 03 25 42 50 50.')).toEqual([
      { texte: 'Écrire à ' },
      { texte: 'a.b@culture.gouv.fr', lien: 'mailto:a.b@culture.gouv.fr' },
      { texte: ' ou au ' },
      { texte: '03 25 42 50 50', lien: 'tel:0325425050' },
      { texte: '.' },
    ]);
  });
});
