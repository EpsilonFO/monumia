import { describe, expect, it } from 'vitest';
import { OWNERSHIP_TYPES, PROTECTION_LEVELS, TYPES_EDIFICE } from '@/constants/monument-options';
import {
  GROUPES_PROPRIETAIRE,
  GROUPES_PROTECTION,
  GROUPES_SIECLE,
  GROUPES_TYPE_EDIFICE,
  SIECLE_AVANT,
  TEXTE_AVANT,
  affectationApplicable,
  appliquerMerimee,
  architectureRomaneApplicable,
  avecProtection,
  avecTypesEdifice,
  basculerChoix,
  champsManquants,
  ficheDepuisMerimee,
  formaterSiecles,
  indexDeRecherche,
  lireSiecles,
  phraseManquants,
  pourcentageRempli,
  sectionsRemplies,
  libellesProprietaires,
  libellesTypesEdifice,
  proprietairesCoches,
  typesCoches,
  typesEdificeDepuisDenomination,
  type FicheMonument,
  champsARemplir,
  groupesProprietaire,
  typesEdificeDepuisNom,
} from '@/lib/fiche-monument';
import type { MerimeeRecord } from '@/types';

const valeursDe = (groupes: typeof GROUPES_PROTECTION) =>
  groupes.flatMap((g) => g.options.map((o) => o.value));

const COMPLETE: FicheMonument = {
  nom: 'Église Saint-Martin',
  commune: 'Valognes',
  etatConservation: 'mauvais',
  protection: 'inscrit',
  proprietaire: ['public_commune'],
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
    // Protégé : 10 champs (type d'édifice compris), 5 remplis.
    expect(pourcentageRempli(COMPLETE)).toBe(50);
    // Non protégé : 8 champs, 5 remplis.
    expect(pourcentageRempli({ ...COMPLETE, protection: 'non_protege' })).toBe(63);
    expect(
      pourcentageRempli({
        ...COMPLETE,
        typeEdifice: ['eglise'],
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

describe("type d'édifice", () => {
  it('propose chaque type une fois, et rien de plus', () => {
    const valeurs = GROUPES_TYPE_EDIFICE.flatMap((g) => g.options.map((o) => o.value));
    expect(new Set(valeurs).size).toBe(valeurs.length);
    expect([...valeurs].sort()).toEqual(TYPES_EDIFICE.map((t) => t.value).sort());
  });

  it("n'écrit pas de tiret cadratin dans les libellés", () => {
    for (const g of GROUPES_TYPE_EDIFICE) {
      for (const o of g.options) expect(`${o.label} ${o.hint ?? ''}`).not.toContain('—');
    }
  });

  it('lit les types cochés, dédoublonnés, et une chaîne seule comme un type', () => {
    expect(typesCoches({})).toEqual([]);
    expect(typesCoches({ typeEdifice: null })).toEqual([]);
    expect(typesCoches({ typeEdifice: ['chateau', 'chapelle', 'chateau'] })).toEqual([
      'chateau',
      'chapelle',
    ]);
    // Brouillon invité d'avant le choix multiple.
    expect(typesCoches({ typeEdifice: 'eglise' as unknown as FicheMonument['typeEdifice'] })).toEqual([
      'eglise',
    ]);
  });

  it("propose une précision dès qu'un type coché l'admet", () => {
    expect(affectationApplicable({ typeEdifice: ['eglise'] })).toBe(true);
    expect(affectationApplicable({ typeEdifice: ['chateau'] })).toBe(false);
    expect(affectationApplicable({ typeEdifice: ['chateau', 'chapelle'] })).toBe(true);
    expect(affectationApplicable({})).toBe(false);
    expect(architectureRomaneApplicable({ typeEdifice: ['chateau', 'lavoir_fontaine'] })).toBe(true);
    expect(architectureRomaneApplicable({ typeEdifice: ['lavoir_fontaine'] })).toBe(false);
  });

  it('vide les précisions quand plus aucun type ne les admet, avec null pour effacer en base', () => {
    const domaine: FicheMonument = {
      typeEdifice: ['chateau', 'chapelle'],
      affecteAuCulte: true,
      architectureRomane: true,
    };
    // Retirer le château : la chapelle garde les deux précisions.
    expect(avecTypesEdifice(domaine, ['chapelle'])).toEqual({
      typeEdifice: ['chapelle'],
      affecteAuCulte: true,
      architectureRomane: true,
    });
    // Retirer la chapelle : le château garde le roman, pas l'affectation.
    expect(avecTypesEdifice(domaine, ['chateau'])).toEqual({
      typeEdifice: ['chateau'],
      affecteAuCulte: null,
      architectureRomane: true,
    });
    // Plus rien de coché : null partout (la base refuse un tableau vide).
    expect(avecTypesEdifice(domaine, [])).toEqual({
      typeEdifice: null,
      affecteAuCulte: null,
      architectureRomane: null,
    });
  });

  it("affiche les libellés dans l'ordre du menu", () => {
    expect(libellesTypesEdifice({ typeEdifice: ['pigeonnier', 'chateau'] })).toEqual([
      'Château, château fort',
      'Pigeonnier, colombier',
    ]);
  });

  it('lit chaque terme reconnu d’une dénomination Mérimée', () => {
    expect(typesEdificeDepuisDenomination('église')).toEqual(['eglise']);
    expect(typesEdificeDepuisDenomination('Cathédrale')).toEqual(['eglise']);
    expect(typesEdificeDepuisDenomination('moulin à farine')).toEqual(['moulin']);
    expect(typesEdificeDepuisDenomination('croix de chemin')).toEqual(['croix_calvaire']);
    expect(typesEdificeDepuisDenomination('hôtel')).toEqual(['hotel_particulier']);
    expect(typesEdificeDepuisDenomination('hôtel de ville')).toEqual(['edifice_public']);
    expect(typesEdificeDepuisDenomination('château;chapelle')).toEqual(['chateau', 'chapelle']);
    expect(typesEdificeDepuisDenomination('château ; chapelle ; château')).toEqual([
      'chateau',
      'chapelle',
    ]);
  });

  it('laisse de côté les termes ambigus', () => {
    // Temple antique ou protestant, immeuble d'habitation ou non.
    expect(typesEdificeDepuisDenomination('temple')).toEqual([]);
    expect(typesEdificeDepuisDenomination('immeuble')).toEqual([]);
    expect(typesEdificeDepuisDenomination('monument')).toEqual([]);
    expect(typesEdificeDepuisDenomination('église;cimetière')).toEqual(['eglise']);
    expect(typesEdificeDepuisDenomination(undefined)).toEqual([]);
    expect(typesEdificeDepuisDenomination('')).toEqual([]);
  });
});

describe('propriétaires', () => {
  it('lit les propriétaires cochés, dédoublonnés, et une chaîne seule comme un propriétaire', () => {
    expect(proprietairesCoches({})).toEqual([]);
    expect(
      proprietairesCoches({ proprietaire: ['public_commune', 'association', 'public_commune'] }),
    ).toEqual(['public_commune', 'association']);
    // Brouillon invité ou cache d'avant le choix multiple.
    expect(
      proprietairesCoches({ proprietaire: 'prive_sci' as unknown as FicheMonument['proprietaire'] }),
    ).toEqual(['prive_sci']);
    expect(
      proprietairesCoches({ proprietaire: ['inconnu'] as unknown as FicheMonument['proprietaire'] }),
    ).toEqual([]);
  });

  it('exige au moins un propriétaire', () => {
    expect(champsManquants({ ...COMPLETE, proprietaire: [] })).toEqual(['le type de propriétaire']);
    expect(sectionsRemplies({ ...COMPLETE, proprietaire: [] })[2]).toBe(false);
    expect(
      champsManquants({ ...COMPLETE, proprietaire: ['public_commune', 'prive_personne_physique'] }),
    ).toEqual([]);
  });

  it('affiche les libellés dans l’ordre de la fiche', () => {
    expect(libellesProprietaires({ proprietaire: ['association', 'public_commune'] })).toEqual([
      'Association',
      'Commune',
    ]);
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
      proprietaire: ['public_commune'],
    });
    // Sans dénomination, le type se lit en tête du titre (« Église Saint-Malo »).
    expect(fiche.typeEdifice).toEqual(['eglise']);
    // La dénomination, quand elle existe, l'emporte sur le titre.
    expect(
      ficheDepuisMerimee({ ...record, denomination_de_l_edifice: 'château;chapelle' }).typeEdifice,
    ).toEqual(['chateau', 'chapelle']);
  });

  it('coche chaque propriétaire que le statut Mérimée énumère', () => {
    const fiche = ficheDepuisMerimee({
      ...record,
      statut_juridique_de_l_edifice: 'propriété de la commune ; propriété privée',
    });
    expect(fiche.proprietaire).toEqual(['public_commune', 'prive_personne_physique']);
    expect(
      ficheDepuisMerimee({ ...record, statut_juridique_de_l_edifice: undefined }).proprietaire,
    ).toBeUndefined();
  });

  it("remplace les types d'édifice, et ne garde leurs précisions que s'ils ne changent pas", () => {
    const avant: FicheMonument = { typeEdifice: ['chapelle', 'chateau'], affecteAuCulte: false };
    const memes = ficheDepuisMerimee({ ...record, denomination_de_l_edifice: 'château;chapelle' });
    expect(appliquerMerimee(avant, memes)).toMatchObject({
      typeEdifice: ['chateau', 'chapelle'],
      affecteAuCulte: false,
    });
    const chateau = ficheDepuisMerimee({ ...record, denomination_de_l_edifice: 'château' });
    const apres = appliquerMerimee(avant, chateau);
    expect(apres.typeEdifice).toEqual(['chateau']);
    expect(apres.affecteAuCulte).toBeUndefined();
    // Une notice muette (ni dénomination, ni type en tête du titre) efface les
    // types d'une notice précédente.
    const muette = ficheDepuisMerimee({ ...record, titre_editorial_de_la_notice: 'Notre-Dame de Bon-Secours' });
    expect(appliquerMerimee(avant, muette).typeEdifice).toBeUndefined();
  });

  it("garde l'état saisi, et le propriétaire quand la notice ne le dit pas", () => {
    const avant: FicheMonument = {
      nom: 'Autre',
      etatConservation: 'peril',
      proprietaire: ['association'],
      dateProtection: '2001-01-01',
    };
    const inconnu = ficheDepuisMerimee({ ...record, statut_juridique_de_l_edifice: undefined, date_et_typologie_de_la_protection: undefined });
    const apres = appliquerMerimee(avant, inconnu);
    expect(apres.nom).toBe('Église Saint-Malo');
    expect(apres.etatConservation).toBe('peril');
    expect(apres.proprietaire).toEqual(['association']);
    // Une date d'un autre monument ne survit pas.
    expect(apres.dateProtection).toBeUndefined();

    expect(appliquerMerimee(avant, ficheDepuisMerimee(record)).proprietaire).toEqual([
      'public_commune',
    ]);
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

describe('typesEdificeDepuisNom', () => {
  it('reconnaît le type en tête du nom, sans accents ni majuscules', () => {
    expect(typesEdificeDepuisNom('chateau de paley')).toEqual(['chateau']);
    expect(typesEdificeDepuisNom('Église Saint-Martin')).toEqual(['eglise']);
    expect(typesEdificeDepuisNom('Lavoir du Pré')).toEqual(['lavoir_fontaine']);
    expect(typesEdificeDepuisNom('Le Moulin de Maître Cornille')).toEqual(['moulin']);
    expect(typesEdificeDepuisNom('Croix de la Mission')).toEqual(['croix_calvaire']);
  });

  it('préfère le terme le plus long', () => {
    expect(typesEdificeDepuisNom('Hôtel de Ville de Lyon')).toEqual(['edifice_public']);
    expect(typesEdificeDepuisNom('Hôtel de Sully')).toEqual(['hotel_particulier']);
    expect(typesEdificeDepuisNom('Hôtel-Dieu de Beaune')).toEqual(['hopital']);
  });

  it("exige un mot entier et ne devine pas ce qu'il ne connaît pas", () => {
    expect(typesEdificeDepuisNom('Forteresse de Salses')).toEqual([]);
    expect(typesEdificeDepuisNom('Notre-Dame de Bon-Secours')).toEqual([]);
    expect(typesEdificeDepuisNom('Maison forte de Reculfoz')).toEqual([]);
    expect(typesEdificeDepuisNom('')).toEqual([]);
    expect(typesEdificeDepuisNom(undefined)).toEqual([]);
  });
});

describe('champsARemplir', () => {
  it("signale toujours l'état du bâtiment, et les précisions d'une église", () => {
    const fiche = {
      nom: 'Église Saint-Martin',
      commune: 'Tours',
      protection: 'classe' as const,
      proprietaire: ['public_commune' as const],
      typeEdifice: ['eglise' as const],
    };
    expect([...champsARemplir(fiche)].sort()).toEqual(
      ['affecteAuCulte', 'architectureRomane', 'etatConservation'].sort(),
    );
  });

  it("ne demande pas les précisions d'un lavoir, et signale un type manquant", () => {
    const fiche = {
      nom: 'Pont Neuf',
      commune: 'Paris',
      protection: 'classe' as const,
      proprietaire: ['public_commune' as const],
      etatConservation: 'bon' as const,
    };
    expect([...champsARemplir(fiche)]).toEqual(['typeEdifice']);
  });

  it('une précision répondue « non » est remplie', () => {
    const fiche = { typeEdifice: ['chapelle' as const], affecteAuCulte: false, architectureRomane: null };
    const vides = champsARemplir(fiche);
    expect(vides.has('affecteAuCulte')).toBe(false);
    expect(vides.has('architectureRomane')).toBe(true);
  });
});

describe('groupesProprietaire', () => {
  const valeurs = (f: Parameters<typeof groupesProprietaire>[0]) =>
    groupesProprietaire(f).flatMap((g) => g.options.map((o) => o.value));

  it('ne propose plus « Propriété mixte »', () => {
    expect(valeurs({})).not.toContain('mixte');
    expect(valeurs({})).toContain('association');
  });

  it("la garde quand elle est cochée (Mérimée, fiche ancienne), pour qu'on puisse la retirer", () => {
    expect(valeurs({ proprietaire: ['mixte'] })).toContain('mixte');
  });
});
