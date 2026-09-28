import { describe, expect, it } from 'vitest';
import { OWNERSHIP_TYPES, PROTECTION_LEVELS } from '@/constants/monument-options';
import {
  GROUPES_PROPRIETAIRE,
  GROUPES_PROTECTION,
  GROUPES_SIECLE,
  SIECLE_AVANT,
  TEXTE_AVANT,
  appliquerMerimee,
  avecProtection,
  basculerChoix,
  champsManquants,
  ficheDepuisMerimee,
  formaterSiecles,
  indexDeRecherche,
  lireSiecles,
  phraseManquants,
  pourcentageRempli,
  sectionsRemplies,
  type FicheMonument,
} from '@/lib/fiche-monument';
import type { MerimeeRecord } from '@/types';

const valeursDe = (groupes: typeof GROUPES_PROTECTION) =>
  groupes.flatMap((g) => g.options.map((o) => o.value));

const COMPLETE: FicheMonument = {
  nom: 'Église Saint-Martin',
  commune: 'Valognes',
  etatConservation: 'mauvais',
  protection: 'inscrit',
  proprietaire: 'public_commune',
};

describe('regroupements', () => {
  it('range chaque niveau de protection une seule fois', () => {
    const valeurs = valeursDe(GROUPES_PROTECTION);
    expect([...valeurs].sort()).toEqual(PROTECTION_LEVELS.map((p) => p.value).sort());
  });

  it('range les dix types de propriétaire une seule fois, avec leurs libellés', () => {
    const valeurs = valeursDe(GROUPES_PROPRIETAIRE);
    expect(valeurs).toHaveLength(10);
    expect([...valeurs].sort()).toEqual(OWNERSHIP_TYPES.map((o) => o.value).sort());
    for (const g of GROUPES_PROPRIETAIRE) {
      for (const o of g.options) {
        expect(o.label).toBe(OWNERSHIP_TYPES.find((t) => t.value === o.value)?.label);
      }
    }
  });
});

describe('basculerChoix', () => {
  it('ajoute et retire', () => {
    expect(basculerChoix([], 'XIIe')).toEqual(['XIIe']);
    expect(basculerChoix(['XIIe', 'XVe'], 'XIIe')).toEqual(['XVe']);
  });

  it("une valeur exclusive remplace tout, et s'efface devant une autre", () => {
    expect(basculerChoix(['XIIe', 'XVe'], SIECLE_AVANT, [SIECLE_AVANT])).toEqual([SIECLE_AVANT]);
    expect(basculerChoix([SIECLE_AVANT], 'XIIe', [SIECLE_AVANT])).toEqual(['XIIe']);
  });
});

describe('siècles', () => {
  it('écrit un texte que le moteur lit (ordinal romain suivi de « siècle »)', () => {
    expect(formaterSiecles([])).toBe('');
    expect(formaterSiecles(['XVe'])).toBe('XVe siècle');
    expect(formaterSiecles(['XVe', 'XIIe'])).toBe('XIIe et XVe siècles');
    expect(formaterSiecles(['XIe', 'XIIe', 'XIIIe'])).toBe('XIe - XIIIe siècle');
    expect(formaterSiecles(['XIe', 'XIIe', 'XIIIe', 'XVIIe'])).toBe('XIe - XIIIe et XVIIe siècles');
    expect(formaterSiecles(['XIIe', 'XIIIe', 'XVe'])).toBe('XIIe, XIIIe et XVe siècles');
  });

  it("« Avant l'an mil » ne porte aucun ordinal, et l'emporte", () => {
    expect(formaterSiecles([SIECLE_AVANT])).toBe(TEXTE_AVANT);
    expect(TEXTE_AVANT).not.toMatch(/[ivx]+e|\d/i);
  });

  it('reste sous les 40 caractères de la route invitée, même très éclatée', () => {
    const eclatee = ['XIe', 'XIIIe', 'XVe', 'XVIIe', 'XIXe', 'XXIe'];
    const texte = formaterSiecles(eclatee);
    expect(texte.length).toBeLessThanOrEqual(40);
    expect(texte.endsWith(' s.')).toBe(true);
    expect(lireSiecles(texte)).toEqual(eclatee);
  });

  it('relit toutes les sélections qu’il écrit', () => {
    const options = GROUPES_SIECLE[0].options.map((o) => o.value).filter((v) => v !== SIECLE_AVANT);
    // Toutes les paires, et toutes les fenêtres consécutives.
    for (let i = 0; i < options.length; i++) {
      for (let j = i; j < options.length; j++) {
        const paire = i === j ? [options[i]] : [options[i], options[j]];
        expect(lireSiecles(formaterSiecles(paire))).toEqual(paire);
        const fenetre = options.slice(i, j + 1);
        expect(lireSiecles(formaterSiecles(fenetre))).toEqual(fenetre);
      }
    }
    expect(lireSiecles(TEXTE_AVANT)).toEqual([SIECLE_AVANT]);
    expect(lireSiecles('')).toEqual([]);
    expect(lireSiecles(undefined)).toEqual([]);
  });

  it('ne relit pas un texte Mérimée : il reste un texte libre', () => {
    expect(lireSiecles('2e moitié 19e siècle')).toBeNull();
    expect(lireSiecles('15e siècle')).toBeNull();
    expect(lireSiecles('12e s.;13e s.')).toBeNull();
    // Même siècles, autre écriture : on ne la réécrit pas en douce.
    expect(lireSiecles('XIIe siècle, XVe siècle')).toBeNull();
    expect(lireSiecles('XIIe - XIIIe siècle')).toBeNull();
  });
});

describe('complétude', () => {
  it('exige nom, commune, état, protection et propriétaire', () => {
    expect(champsManquants({})).toEqual([
      'le nom',
      'la commune',
      "l'état du bâtiment",
      'la protection',
      'le type de propriétaire',
    ]);
    expect(champsManquants({ ...COMPLETE, nom: '   ' })).toEqual(['le nom']);
    expect(champsManquants(COMPLETE)).toEqual([]);
  });

  it('écrit la phrase sous le bouton', () => {
    expect(phraseManquants({ nom: 'X', commune: 'Y', etatConservation: 'bon' })).toBe(
      'Il manque la protection, le type de propriétaire.',
    );
    expect(phraseManquants(COMPLETE)).toBeNull();
  });

  it('compte la jauge sur nos champs, sans date ni détail pour un bien non protégé', () => {
    expect(pourcentageRempli({})).toBe(0);
    // Protégé : 9 champs, 5 remplis.
    expect(pourcentageRempli(COMPLETE)).toBe(56);
    // Non protégé : 7 champs, 5 remplis.
    expect(pourcentageRempli({ ...COMPLETE, protection: 'non_protege' })).toBe(71);
    expect(
      pourcentageRempli({
        ...COMPLETE,
        siecleConstruction: 'XVe siècle',
        descriptionGenerale: 'Nef romane',
        dateProtection: '1928-06-16',
        typeProtection: 'Inscrit MH',
      }),
    ).toBe(100);
  });

  it('colore une section quand ses champs principaux sont remplis', () => {
    expect(sectionsRemplies({})).toEqual([false, false, false]);
    expect(sectionsRemplies(COMPLETE)).toEqual([false, true, true]);
    expect(sectionsRemplies({ ...COMPLETE, siecleConstruction: 'XVe siècle' })).toEqual([
      true,
      true,
      true,
    ]);
  });

  it('vide date et détail en passant à « non protégé »', () => {
    expect(avecProtection('non_protege')).toEqual({
      protection: 'non_protege',
      dateProtection: '',
      typeProtection: '',
    });
    expect(avecProtection('classe')).toEqual({ protection: 'classe' });
  });
});

describe('Mérimée', () => {
  const record: MerimeeRecord = {
    reference: 'PA00110812',
    region: 'Normandie',
    commune_forme_index: 'Valognes',
    departement_en_lettres: 'Manche',
    typologie_de_la_protection: 'inscrit MH',
    titre_editorial_de_la_notice: 'Église Saint-Malo',
    date_et_typologie_de_la_protection: '1928/06/16 : inscrit MH',
    format_abrege_du_siecle_de_construction: '2e moitié 19e siècle',
    statut_juridique_de_l_edifice: 'propriété de la commune',
    cog_insee_lors_de_la_protection: '50615',
  };

  it('remplit la fiche depuis la notice', () => {
    const fiche = ficheDepuisMerimee(record);
    expect(fiche).toMatchObject({
      nom: 'Église Saint-Malo',
      referenceMerimee: 'PA00110812',
      commune: 'Valognes',
      codeInsee: '50615',
      region: 'normandie',
      protection: 'inscrit',
      dateProtection: '1928-06-16',
      typeProtection: '1928/06/16 : inscrit MH',
      siecleConstruction: '2e moitié 19e siècle',
      proprietaire: 'public_commune',
    });
  });

  it("garde l'état saisi, et le propriétaire quand la notice ne le dit pas", () => {
    const avant: FicheMonument = {
      nom: 'Autre',
      etatConservation: 'peril',
      proprietaire: 'association',
      dateProtection: '2001-01-01',
    };
    const inconnu = ficheDepuisMerimee({ ...record, statut_juridique_de_l_edifice: undefined, date_et_typologie_de_la_protection: undefined });
    const apres = appliquerMerimee(avant, inconnu);
    expect(apres.nom).toBe('Église Saint-Malo');
    expect(apres.etatConservation).toBe('peril');
    expect(apres.proprietaire).toBe('association');
    // Une date d'un autre monument ne survit pas.
    expect(apres.dateProtection).toBeUndefined();

    expect(appliquerMerimee(avant, ficheDepuisMerimee(record)).proprietaire).toBe('public_commune');
  });
});

describe('indexDeRecherche', () => {
  it('ignore accents, casse, tirets et apostrophes', () => {
    expect(indexDeRecherche('Saint-Étienne', 'etienne')).toBe(6);
    expect(indexDeRecherche('Saint-Étienne', 'saint e')).toBe(0);
    expect(indexDeRecherche("L'Abergement", 'l ab')).toBe(0);
    expect(indexDeRecherche('Valognes', 'zzz')).toBe(-1);
    expect(indexDeRecherche('Valognes', '  ')).toBe(-1);
  });
});
