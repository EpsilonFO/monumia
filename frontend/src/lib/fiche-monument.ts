/**
 * La fiche d'un monument telle que la saisit l'écran de création (maquette
 * « monumia-nouveau-monument » du designer, septembre 2026) : les regroupements
 * de ses menus, le siècle de construction, la jauge, les champs manquants.
 *
 * Tout ce qui décide est ici, sans React, pour être testé. Les VALEURS sont
 * celles du produit (`ProtectionLevel`, `OwnershipType`, `ETATS_CONSERVATION`) :
 * la maquette n'a donné que la mise en page et les regroupements.
 */
import { OWNERSHIP_TYPES, TYPES_EDIFICE, type TypeEdifice } from '@/constants/monument-options';
import { REGIONS } from '@/constants/regions';
import type { MerimeeRecord, Monument, OwnershipType, ProtectionLevel, Region } from '@/types';

export type FicheMonument = Partial<Monument>;

export interface OptionChoix {
  value: string;
  label: string;
  /** Précision sous le libellé, en petit. */
  hint?: string;
}

export interface GroupeChoix {
  /** Intitulé en capitales au-dessus du groupe ; vide = pas d'intitulé. */
  titre: string;
  options: readonly OptionChoix[];
}

// --- Protection -------------------------------------------------------------

/**
 * Les cinq niveaux de `ProtectionLevel`, dans les trois groupes de la maquette.
 * Les options qu'elle ajoutait (partiellement classé ou inscrit, site classé au
 * titre des paysages, « je ne sais pas ») n'existent pas dans le modèle : aucune
 * aide ne les lit, elles sont retirées.
 */
export const GROUPES_PROTECTION: readonly GroupeChoix[] = [
  {
    titre: 'Monument historique',
    options: [
      { value: 'classe', label: 'Classé monument historique' },
      { value: 'inscrit', label: 'Inscrit monument historique' },
    ],
  },
  {
    titre: 'Protection du lieu',
    options: [
      { value: 'spr', label: 'Site patrimonial remarquable (SPR)' },
      {
        value: 'abords',
        label: "Abords d'un monument historique",
        hint: "Dans le périmètre de protection d'un monument historique",
      },
    ],
  },
  {
    titre: 'Aucune',
    options: [
      {
        value: 'non_protege',
        label: 'Non protégé',
        hint: 'Ni classé, ni inscrit, ni en abords, ni en SPR',
      },
    ],
  },
];

// --- Propriétaire -----------------------------------------------------------

/**
 * Les dix `OwnershipType`, rangés par nature. Libellés d'`OWNERSHIP_TYPES`,
 * repris tels quels : ce sont ceux de la fiche du monument, qui les affiche
 * ensuite.
 */
const GROUPES_PROPRIETAIRE_CLES: readonly { titre: string; valeurs: readonly string[] }[] = [
  { titre: 'Propriétaires privés', valeurs: ['prive_personne_physique', 'prive_sci'] },
  {
    titre: 'Propriétaires publics',
    valeurs: [
      'public_commune',
      'public_epci',
      'public_departement',
      'public_region',
      'public_etat',
      'syndicat_mixte',
    ],
  },
  { titre: 'Autres propriétaires', valeurs: ['association', 'mixte'] },
];

export const GROUPES_PROPRIETAIRE: readonly GroupeChoix[] = GROUPES_PROPRIETAIRE_CLES.map(
  ({ titre, valeurs }) => ({
    titre,
    options: valeurs.map((value) => {
      const type = OWNERSHIP_TYPES.find((o) => o.value === value);
      return { value, label: type?.label ?? value };
    }),
  }),
);

/**
 * Valeurs qu'on ne propose plus au choix mais qui restent LISIBLES : « Propriété
 * mixte » fait doublon avec le choix multiple (2026-09-30) et ne dit à aucune
 * aide qui dépose. Mérimée peut encore la poser (statut « mixte »), et une fiche
 * ancienne la porter : elle reste alors dans le menu, cochée, pour pouvoir être
 * retirée.
 */
const PROPRIETAIRES_MASQUES: ReadonlySet<string> = new Set(['mixte']);

/** Les groupes du menu propriétaire pour cette fiche : sans les valeurs masquées, sauf cochées. */
export function groupesProprietaire(fiche: FicheMonument): readonly GroupeChoix[] {
  const coches = new Set<string>(proprietairesCoches(fiche));
  return GROUPES_PROPRIETAIRE.map((g) => ({
    ...g,
    options: g.options.filter((o) => !PROPRIETAIRES_MASQUES.has(o.value) || coches.has(o.value)),
  }));
}

// --- Type d'édifice ---------------------------------------------------------

/**
 * Les types de `TYPES_EDIFICE`, rangés par famille. Chaque code n'apparaît
 * qu'une fois (vérifié par le test) : un code oublié serait impossible à
 * choisir, et les questions qu'il répond resteraient posées.
 */
const GROUPES_TYPE_EDIFICE_CLES: readonly { titre: string; valeurs: readonly TypeEdifice[] }[] = [
  {
    titre: 'Édifices religieux',
    valeurs: [
      'eglise',
      'chapelle',
      'abbaye_couvent',
      'temple',
      'synagogue',
      'croix_calvaire',
      'autre_religieux',
    ],
  },
  {
    titre: 'Châteaux et demeures',
    valeurs: ['chateau', 'manoir_demeure', 'hotel_particulier', 'maison'],
  },
  {
    titre: 'Édifices civils',
    valeurs: ['edifice_public', 'hopital', 'halle', 'patrimoine_industriel'],
  },
  {
    titre: 'Patrimoine rural',
    valeurs: ['ferme', 'moulin', 'lavoir_fontaine', 'pigeonnier', 'petit_patrimoine'],
  },
  {
    titre: 'Ouvrages, sites et mémoire',
    valeurs: [
      'fortification',
      'pont',
      'jardin',
      'site_archeologique',
      'monument_aux_morts',
      'monument_commemoratif',
    ],
  },
  { titre: 'Autre', valeurs: ['autre'] },
];

export const GROUPES_TYPE_EDIFICE: readonly GroupeChoix[] = GROUPES_TYPE_EDIFICE_CLES.map(
  ({ titre, valeurs }) => ({
    titre,
    options: valeurs.map((value) => {
      const type = TYPES_EDIFICE.find((t) => t.value === value);
      return { value, label: type?.label ?? value, hint: type && 'hint' in type ? type.hint : undefined };
    }),
  }),
);

/**
 * Les types où l'affectation au culte a un sens. Miroir de `labels.py` (même
 * nom), vérifié par `tests/test_type_edifice.py`. Hors de ces types, la
 * précision n'est pas proposée, et le serveur l'efface.
 */
export const TYPES_AVEC_AFFECTATION_CULTE: ReadonlySet<TypeEdifice> = new Set<TypeEdifice>([
  'eglise',
  'chapelle',
  'abbaye_couvent',
  'temple',
  'synagogue',
  'autre_religieux',
]);

/**
 * L'architecture romane suit le DOMAINE Mérimée du bien (2026-10-06), pas le
 * type coché : la précision n'est proposée qu'aux édifices que Mérimée range en
 * « architecture religieuse », seule ou combinée (« architecture
 * religieuse;architecture militaire »). Ailleurs, la question reste posée au
 * questionnaire si une aide la cite. Miroir de `labels.py`
 * (`architecture_romane_applicable`), vérifié par `tests/test_type_edifice.py`.
 */
export const DOMAINE_ARCHITECTURE_RELIGIEUSE = 'architecture religieuse';

/**
 * Les types cochés, dédoublonnés, dans l'ordre. Choix multiple depuis le
 * 2026-09-30 : un domaine réunit château, chapelle, pigeonnier. Une chaîne
 * seule (brouillon invité ou cache d'avant le passage en liste) vaut un type.
 */
export function typesCoches(fiche: FicheMonument): TypeEdifice[] {
  const brut: unknown = fiche.typeEdifice;
  const liste = typeof brut === 'string' ? [brut] : Array.isArray(brut) ? brut : [];
  const connus = new Set<string>(TYPES_EDIFICE.map((t) => t.value));
  return [...new Set(liste.filter((t): t is TypeEdifice => typeof t === 'string' && connus.has(t)))];
}

/** La précision est proposée dès qu'AU MOINS un type coché l'admet. */
export function affectationApplicable(fiche: FicheMonument): boolean {
  return typesCoches(fiche).some((t) => TYPES_AVEC_AFFECTATION_CULTE.has(t));
}

/** Le domaine Mérimée contient-il « architecture religieuse » ? */
export function architectureRomaneApplicable(fiche: FicheMonument): boolean {
  const domaine = fiche.merimeeDomaine;
  if (typeof domaine !== 'string') return false;
  return domaine
    .split(';')
    .some((terme) => terme.trim().toLowerCase() === DOMAINE_ARCHITECTURE_RELIGIEUSE);
}

/**
 * Changer les types cochés : l'affectation au culte est vidée si aucun type
 * restant ne l'admet. Le style roman ne dépend pas du type, il n'est pas
 * touché. `null` et non `undefined`, pour que l'édition d'une fiche existante
 * les efface aussi en base (un `undefined` ne part pas dans le JSON). Aucun
 * type coché vaut `null` : la base refuse un tableau vide.
 */
export function avecTypesEdifice(fiche: FicheMonument, valeurs: readonly string[]): FicheMonument {
  const types = typesCoches({ typeEdifice: valeurs as TypeEdifice[] });
  const suivante: FicheMonument = { typeEdifice: types };
  return {
    typeEdifice: types.length > 0 ? types : null,
    affecteAuCulte: affectationApplicable(suivante) ? (fiche.affecteAuCulte ?? null) : null,
  };
}

/** Les libellés des types cochés, dans l'ordre du menu, pour l'affichage. */
export function libellesTypesEdifice(fiche: FicheMonument): string[] {
  const coches = new Set(typesCoches(fiche));
  return TYPES_EDIFICE.filter((t) => coches.has(t.value)).map((t) => t.label);
}

/**
 * Les propriétaires cochés, dédoublonnés, dans l'ordre. Choix multiple depuis
 * le 2026-09-30 : une aide est proposée dès qu'UN d'eux peut la déposer (le
 * moteur évalue l'aide une fois par propriétaire). Une chaîne seule (brouillon
 * invité ou cache d'avant le passage en liste) vaut un propriétaire.
 */
export function proprietairesCoches(fiche: FicheMonument): OwnershipType[] {
  const brut: unknown = fiche.proprietaire;
  const liste = typeof brut === 'string' ? [brut] : Array.isArray(brut) ? brut : [];
  const connus = new Set<string>(OWNERSHIP_TYPES.map((o) => o.value));
  return [
    ...new Set(liste.filter((p): p is OwnershipType => typeof p === 'string' && connus.has(p))),
  ];
}

/** Les libellés des propriétaires cochés, dans l'ordre de la fiche. */
export function libellesProprietaires(fiche: FicheMonument): string[] {
  return proprietairesCoches(fiche).map(
    (p) => OWNERSHIP_TYPES.find((o) => o.value === p)?.label ?? p,
  );
}

/** Libellé d'une valeur dans des groupes de choix (la valeur brute à défaut). */
export function libelleChoix(groupes: readonly GroupeChoix[], value: string | undefined): string {
  if (!value) return '';
  for (const g of groupes) {
    const o = g.options.find((x) => x.value === value);
    if (o) return o.label;
  }
  return value;
}

/**
 * Ajoute ou retire `valeur` d'une sélection multiple. Une valeur EXCLUSIVE
 * remplace tout, et en choisir une autre la retire (patron de la maquette pour
 * « Non protégé » ou « Je ne sais pas »).
 */
export function basculerChoix(
  selection: readonly string[],
  valeur: string,
  exclusifs: readonly string[] = [],
): string[] {
  if (selection.includes(valeur)) return selection.filter((x) => x !== valeur);
  if (exclusifs.includes(valeur)) return [valeur];
  return [...selection.filter((x) => !exclusifs.includes(x)), valeur];
}

// --- Siècle de construction -------------------------------------------------

/*
 * `monuments.siecle_construction` est un TEXTE libre, et le moteur le lit :
 * `_annee_depuis_siecle` (backend/eligibility_engine.py) en tire le fait
 * `annee_construction` sous forme d'intervalle, en prenant le PREMIER siècle
 * cité (« 14e - 18e siècle » → 1301-1400). Il reconnaît un ordinal arabe ou
 * romain suivi de « siècle(s) » ou « s. », et les chaînes d'ordinaux séparés
 * par une virgule, un tiret ou « et ».
 *
 * Le menu écrit donc une chaîne que ce lecteur comprend (« XIIe siècle »,
 * « XIIe et XVe siècles », « XIe - XIIIe siècle ») et relit la sienne. Tout
 * autre texte (celui de Mérimée, « 2e moitié 19e siècle », souvent plus précis)
 * est conservé tel quel et montré comme texte libre : seul un choix explicite
 * dans le menu le remplace.
 *
 * « Avant l'an mil » ne contient AUCUN ordinal lisible, exprès : « Avant le XIe
 * siècle » serait lu comme le XIe siècle (1001-1100), et un critère « construit
 * avant 1000 » serait tranché à tort. Sans ordinal, le moteur laisse la
 * question de l'année posée. Pour la même raison ce choix est exclusif : cité
 * avec le XIIe, il laisserait le XIIe passer pour le premier siècle.
 */

export const SIECLE_AVANT = 'avant';
export const TEXTE_AVANT = "Avant l'an mil";
const ROMAINS = ['XIe', 'XIIe', 'XIIIe', 'XIVe', 'XVe', 'XVIe', 'XVIIe', 'XVIIIe', 'XIXe', 'XXe', 'XXIe'];

export const GROUPES_SIECLE: readonly GroupeChoix[] = [
  {
    titre: '',
    options: [
      { value: SIECLE_AVANT, label: TEXTE_AVANT },
      ...ROMAINS.map((r) => ({ value: r, label: `${r} siècle` })),
    ],
  },
];
export const SIECLES_EXCLUSIFS: readonly string[] = [SIECLE_AVANT];

/**
 * Plafond de `siecleConstruction` sur le diagnostic invité (`MonumentInvite`,
 * backend/routers/aides.py) : au-delà, la route publique répond 422.
 */
const LONGUEUR_MAX = 40;

/** Siècles choisis → texte de la fiche. Chaîne vide si rien n'est choisi. */
export function formaterSiecles(valeurs: readonly string[]): string {
  if (valeurs.includes(SIECLE_AVANT)) return TEXTE_AVANT;
  const rangs = [...new Set(valeurs.map((v) => ROMAINS.indexOf(v)).filter((i) => i >= 0))].sort(
    (a, b) => a - b,
  );
  if (rangs.length === 0) return '';

  // Trois siècles consécutifs ou plus se disent en fourchette.
  const morceaux: string[] = [];
  let debut = 0;
  for (let i = 1; i <= rangs.length; i++) {
    if (i < rangs.length && rangs[i] === rangs[i - 1] + 1) continue;
    const suite = rangs.slice(debut, i);
    if (suite.length >= 3) morceaux.push(`${ROMAINS[suite[0]]} - ${ROMAINS[suite[suite.length - 1]]}`);
    else morceaux.push(...suite.map((r) => ROMAINS[r]));
    debut = i;
  }

  const corps =
    morceaux.length === 1
      ? morceaux[0]
      : `${morceaux.slice(0, -1).join(', ')} et ${morceaux[morceaux.length - 1]}`;
  const complet = `${corps} ${morceaux.length === 1 ? 'siècle' : 'siècles'}`;
  // « s. » est lu par le moteur comme « siècle » : c'est le seul raccourci qui
  // tienne une sélection très éclatée sous le plafond de la route invitée.
  return complet.length <= LONGUEUR_MAX ? complet : `${corps} s.`;
}

/**
 * Texte de la fiche → siècles du menu, ou `null` si le texte n'est pas un de
 * ceux que le menu écrit (texte Mérimée, saisie ancienne) : il reste alors un
 * texte libre, qu'on ne réécrit pas.
 */
export function lireSiecles(texte: string | undefined): string[] | null {
  const brut = (texte ?? '').trim();
  if (!brut) return [];
  if (brut === TEXTE_AVANT) return [SIECLE_AVANT];
  const corps = brut.replace(/\s+(?:siècles?|s\.)$/, '');
  if (corps === brut) return null;
  const valeurs: string[] = [];
  for (const morceau of corps.split(/, | et /)) {
    const fourchette = morceau.split(' - ');
    const rangs = fourchette.map((r) => ROMAINS.indexOf(r));
    if (rangs.some((r) => r < 0) || rangs.length > 2) return null;
    const [de, a = rangs[0]] = rangs;
    for (let r = de; r <= a; r++) valeurs.push(ROMAINS[r]);
  }
  // Relu seulement si le menu l'aurait écrit à l'identique : sinon, rechoisir
  // la même chose changerait le texte sous les yeux de l'utilisateur.
  return formaterSiecles(valeurs) === brut ? valeurs : null;
}

// --- Complétude -------------------------------------------------------------

const rempli = (v: string | undefined | null) => Boolean(v && v.trim());

/** Un bien non protégé n'a ni date ni détail de protection : ces champs sortent du compte. */
export function protectionApplicable(fiche: FicheMonument): boolean {
  return fiche.protection !== 'non_protege';
}

/**
 * Les champs que compte la jauge « Fiche remplie », requis et facultatifs.
 * Date et détail de la protection n'y figurent que s'ils ont un sens.
 */
export function champsDeLaJauge(fiche: FicheMonument): boolean[] {
  return [
    rempli(fiche.nom),
    rempli(fiche.commune),
    typesCoches(fiche).length > 0,
    rempli(fiche.siecleConstruction),
    Boolean(fiche.etatConservation),
    rempli(fiche.descriptionGenerale),
    Boolean(fiche.protection),
    ...(protectionApplicable(fiche)
      ? [rempli(fiche.dateProtection), rempli(fiche.typeProtection)]
      : []),
    proprietairesCoches(fiche).length > 0,
  ];
}

export function pourcentageRempli(fiche: FicheMonument): number {
  const champs = champsDeLaJauge(fiche);
  return Math.round((champs.filter(Boolean).length / champs.length) * 100);
}

/**
 * Les champs sans lesquels la fiche ne s'enregistre pas, dans l'ordre de
 * l'écran. Ce sont ceux qu'exigeait le formulaire en trois étapes : l'état
 * sanitaire compris, que le wizard projet invité ne rattrape pas.
 */
const REQUIS: readonly { libelle: string; ok: (f: FicheMonument) => boolean }[] = [
  { libelle: 'le nom', ok: (f) => rempli(f.nom) },
  { libelle: 'la commune', ok: (f) => rempli(f.commune) },
  { libelle: "l'état du bâtiment", ok: (f) => Boolean(f.etatConservation) },
  { libelle: 'la protection', ok: (f) => Boolean(f.protection) },
  { libelle: 'le type de propriétaire', ok: (f) => proprietairesCoches(f).length > 0 },
];

export function champsManquants(fiche: FicheMonument): string[] {
  return REQUIS.filter((r) => !r.ok(fiche)).map((r) => r.libelle);
}

/** Phrase sous le bouton : ce qui manque, ou `null` si la fiche est complète. */
export function phraseManquants(fiche: FicheMonument): string | null {
  const manquants = champsManquants(fiche);
  return manquants.length ? `Il manque ${manquants.join(', ')}.` : null;
}

/** Les champs de la fiche qu'un encadré orange peut signaler. */
export type ChampFiche =
  | 'nom'
  | 'commune'
  | 'typeEdifice'
  | 'affecteAuCulte'
  | 'architectureRomane'
  | 'etatConservation'
  | 'protection'
  | 'proprietaire';

/**
 * Ce qui reste à remplir une fois la fiche pré-remplie par Mérimée : les champs
 * requis encore vides, l'état du bâtiment (que Mérimée ne connaît jamais), le
 * type d'édifice s'il n'a pas pu être deviné, et les deux précisions quand un
 * type coché les admet. Les précisions restent facultatives : l'encadré dit
 * qu'une réponse sert, pas qu'elle est exigée.
 */
export function champsARemplir(fiche: FicheMonument): Set<ChampFiche> {
  const vides: [ChampFiche, boolean][] = [
    ['nom', !rempli(fiche.nom)],
    ['commune', !rempli(fiche.commune)],
    ['typeEdifice', typesCoches(fiche).length === 0],
    ['affecteAuCulte', affectationApplicable(fiche) && fiche.affecteAuCulte == null],
    ['architectureRomane', architectureRomaneApplicable(fiche) && fiche.architectureRomane == null],
    ['etatConservation', !fiche.etatConservation],
    ['protection', !fiche.protection],
    ['proprietaire', proprietairesCoches(fiche).length === 0],
  ];
  return new Set(vides.filter(([, vide]) => vide).map(([champ]) => champ));
}

/**
 * Pastille verte d'une section : ses champs principaux sont remplis. Même règle
 * que la maquette, où les champs secondaires (sa « Siècle de la protection »,
 * nos date, détail et description) ne comptent pas.
 */
export function sectionsRemplies(fiche: FicheMonument): [boolean, boolean, boolean] {
  return [
    rempli(fiche.nom) &&
      rempli(fiche.commune) &&
      rempli(fiche.siecleConstruction) &&
      Boolean(fiche.etatConservation),
    Boolean(fiche.protection),
    proprietairesCoches(fiche).length > 0,
  ];
}

/** Changer de protection : passer à « non protégé » vide date et détail. */
export function avecProtection(protection: ProtectionLevel | undefined): FicheMonument {
  return protection === 'non_protege'
    ? { protection, dateProtection: '', typeProtection: '' }
    : { protection };
}

// --- Mérimée ----------------------------------------------------------------

const REGION_LABEL_TO_VALUE: Record<string, string> = Object.fromEntries(
  REGIONS.map((r) => [r.label.toLowerCase(), r.value]),
);

const PROPRIETAIRE_MAP: Record<string, OwnershipType> = {
  commune: 'public_commune',
  communal: 'public_commune',
  'département': 'public_departement',
  departemental: 'public_departement',
  'région': 'public_region',
  regional: 'public_region',
  'état': 'public_etat',
  etat: 'public_etat',
  'propriété privée': 'prive_personne_physique',
  'privé': 'prive_personne_physique',
  prive: 'prive_personne_physique',
  sci: 'prive_sci',
  association: 'association',
  mixte: 'mixte',
};

/**
 * Dénominations Mérimée (premier terme du thésaurus, en minuscules) → type
 * d'édifice. Seules celles qui désignent le type SANS AMBIGUÏTÉ y sont : un
 * type faux répondrait à tort aux questions sur la nature du bien, et
 * écarterait des aides. Laissées de côté exprès : « temple » (aussi le temple
 * antique), « immeuble » (d'habitation ou non), « monument » (sans précision),
 * « maison forte », « tour », « cimetière », « oratoire ».
 */
const DENOMINATIONS_TYPE: Record<string, TypeEdifice> = {
  'église': 'eglise',
  'cathédrale': 'eglise',
  basilique: 'eglise',
  'collégiale': 'eglise',
  chapelle: 'chapelle',
  abbaye: 'abbaye_couvent',
  couvent: 'abbaye_couvent',
  'prieuré': 'abbaye_couvent',
  'établissement conventuel': 'abbaye_couvent',
  synagogue: 'synagogue',
  calvaire: 'croix_calvaire',
  'calvaire monumental': 'croix_calvaire',
  'château': 'chateau',
  'château fort': 'chateau',
  manoir: 'manoir_demeure',
  demeure: 'manoir_demeure',
  // Dans le thésaurus Mérimée, « hôtel » est l'hôtel particulier ; l'hôtel de
  // ville, l'hôtel de voyageurs et l'hôtel-Dieu ont chacun leur terme.
  'hôtel': 'hotel_particulier',
  'hôtel particulier': 'hotel_particulier',
  maison: 'maison',
  mairie: 'edifice_public',
  'hôtel de ville': 'edifice_public',
  'école': 'edifice_public',
  'collège': 'edifice_public',
  'lycée': 'edifice_public',
  'palais de justice': 'edifice_public',
  tribunal: 'edifice_public',
  'préfecture': 'edifice_public',
  'théâtre': 'edifice_public',
  'hôpital': 'hopital',
  hospice: 'hopital',
  'hôtel-dieu': 'hopital',
  maladrerie: 'hopital',
  halle: 'halle',
  'marché couvert': 'halle',
  usine: 'patrimoine_industriel',
  forge: 'patrimoine_industriel',
  'grosse forge': 'patrimoine_industriel',
  filature: 'patrimoine_industriel',
  mine: 'patrimoine_industriel',
  gare: 'patrimoine_industriel',
  ferme: 'ferme',
  grange: 'ferme',
  'édifice agricole': 'ferme',
  moulin: 'moulin',
  lavoir: 'lavoir_fontaine',
  fontaine: 'lavoir_fontaine',
  pigeonnier: 'pigeonnier',
  colombier: 'pigeonnier',
  four: 'petit_patrimoine',
  'four à pain': 'petit_patrimoine',
  puits: 'petit_patrimoine',
  fortification: 'fortification',
  "fortification d'agglomération": 'fortification',
  'édifice fortifié': 'fortification',
  enceinte: 'fortification',
  'porte de ville': 'fortification',
  citadelle: 'fortification',
  fort: 'fortification',
  pont: 'pont',
  aqueduc: 'pont',
  'pont aqueduc': 'pont',
  viaduc: 'pont',
  jardin: 'jardin',
  parc: 'jardin',
  'site archéologique': 'site_archeologique',
  dolmen: 'site_archeologique',
  menhir: 'site_archeologique',
  tumulus: 'site_archeologique',
  'allée couverte': 'site_archeologique',
  oppidum: 'site_archeologique',
  'monument aux morts': 'monument_aux_morts',
  'monument commémoratif': 'monument_commemoratif',
  statue: 'monument_commemoratif',
};

/** Familles reconnues à leur premier mot : « moulin à farine », « croix de chemin ». */
const PREFIXES_TYPE: readonly [string, TypeEdifice][] = [
  ['moulin ', 'moulin'],
  ['croix ', 'croix_calvaire'],
  ['usine ', 'patrimoine_industriel'],
  ['grange ', 'ferme'],
];

function typeDUnTerme(terme: string): TypeEdifice | undefined {
  const t = terme.normalize('NFC').toLowerCase().replace(/’/g, "'").replace(/\s+/g, ' ').trim();
  if (!t) return undefined;
  if (t === 'croix') return 'croix_calvaire';
  return DENOMINATIONS_TYPE[t] ?? PREFIXES_TYPE.find(([p]) => t.startsWith(p))?.[1];
}

/**
 * Les types d'édifice qu'une dénomination Mérimée désigne avec certitude, dans
 * l'ordre de la notice (liste vide si aucun). Chaque terme de la dénomination
 * (« château ; chapelle ») est lu à part, et ceux qu'on ignore exprès le
 * restent : « église ; cimetière » ne donne que l'église.
 */
export function typesEdificeDepuisDenomination(denomination: string | undefined): TypeEdifice[] {
  const reconnus = (denomination ?? '')
    .split(';')
    .map(typeDUnTerme)
    .filter((t): t is TypeEdifice => t !== undefined);
  return [...new Set(reconnus)];
}

const sansAccents = (x: string) => x.normalize('NFD').replace(/[\u0300-\u036f]/g, '');

/**
 * Les termes de `DENOMINATIONS_TYPE` sans accents, du plus long au plus court :
 * « hôtel de ville » doit l'emporter sur « hôtel », « château fort » sur
 * « château ».
 */
const TERMES_PAR_LONGUEUR: readonly [string, TypeEdifice][] = [
  ...Object.entries(DENOMINATIONS_TYPE).map(([t, type]) => [sansAccents(t), type] as [string, TypeEdifice]),
  ['croix', 'croix_calvaire'] as [string, TypeEdifice],
].sort(([a], [b]) => b.length - a.length);

/**
 * Débuts de nom qui ressemblent à un type sans en être un : une maison forte
 * n'est pas une maison, un four à chaux pas un four à pain.
 */
const NOMS_TROMPEURS: readonly string[] = ['maison forte', 'four a chaux'];

/**
 * Le type d'édifice que le NOM du monument désigne mot pour mot : « Château de
 * Paley » → château, « Église Saint-Martin » → église, « Lavoir du Pré » →
 * lavoir. Seul le premier mot compte (article compris : « Le Moulin de… »),
 * comparé sans accents ni majuscules à la même liste fermée que les
 * dénominations Mérimée. Un nom qui ne commence pas par un type connu ne donne
 * rien : « Notre-Dame de Bon-Secours » n'est pas classé à l'aveugle.
 */
export function typesEdificeDepuisNom(nom: string | undefined): TypeEdifice[] {
  let t = sansAccents((nom ?? '').normalize('NFC').toLowerCase())
    .replace(/[’']/g, "'")
    .replace(/\s+/g, ' ')
    .trim();
  t = t.replace(/^(?:le |la |les |l')/, '');
  if (!t || NOMS_TROMPEURS.some((n) => t.startsWith(n))) return [];
  // Le terme doit être un mot entier : « Fortin » n'est pas « fort », et
  // « Hôtel-Dieu » n'est pas « hôtel » (il a son propre terme, trait d'union compris).
  const trouve = TERMES_PAR_LONGUEUR.find(
    ([terme]) => t === terme || (t.startsWith(terme) && /^[\s,]/.test(t.slice(terme.length))),
  );
  return trouve ? [trouve[1]] : [];
}

/**
 * Une notice Mérimée → les champs de la fiche qu'elle remplit. Reprise telle
 * quelle de l'ancien `handleMerimeeSelect` de la page de création.
 */
export function ficheDepuisMerimee(record: MerimeeRecord): FicheMonument {
  const lastOf = (s: string | undefined) => s?.split(';').pop()?.trim() ?? '';

  const typoEntries = (record.typologie_de_la_protection ?? '')
    .split(';')
    .map((s) => s.toLowerCase().trim());
  let protection: ProtectionLevel = 'non_protege';
  for (const t of typoEntries) {
    if (t.includes('classé')) protection = 'classe';
    else if (t.includes('inscrit')) protection = 'inscrit';
  }

  const regionValue = REGION_LABEL_TO_VALUE[record.region?.toLowerCase() ?? ''] ?? '';

  // Le statut Mérimée énumère parfois plusieurs propriétaires (« propriété de
  // la commune ; propriété privée ») : chaque terme reconnu en coche un.
  const proprietaires = [
    ...new Set(
      (record.statut_juridique_de_l_edifice ?? '')
        .split(';')
        .map((terme) => terme.toLowerCase().trim())
        .filter(Boolean)
        .map(
          (statut) =>
            PROPRIETAIRE_MAP[statut] ??
            Object.entries(PROPRIETAIRE_MAP).find(([k]) => statut.includes(k))?.[1],
        )
        .filter((p): p is OwnershipType => p !== undefined),
    ),
  ];

  let dateProtection: string | undefined;
  const lastDateEntry = lastOf(record.date_et_typologie_de_la_protection);
  if (lastDateEntry) {
    const datePart = lastDateEntry.split(':')[0]?.trim() ?? '';
    if (/^\d{4}\/\d{2}\/\d{2}$/.test(datePart)) {
      dateProtection = datePart.replace(/\//g, '-');
    }
  }
  const typeProtection =
    lastOf(record.date_et_typologie_de_la_protection) ||
    lastOf(record.typologie_de_la_protection) ||
    undefined;

  // La dénomination d'abord (le thésaurus Mérimée) ; à défaut, le nom de la
  // notice, qui commence presque toujours par le type (« Château de Paley »).
  const nom = record.titre_editorial_de_la_notice ?? '';
  const parDenomination = typesEdificeDepuisDenomination(record.denomination_de_l_edifice);
  const typesEdifice = parDenomination.length > 0 ? parDenomination : typesEdificeDepuisNom(nom);

  // Matériaux et type de couverture ne sont plus préremplis : leurs colonnes
  // ont été droppées (migration 20260516174303) et aucune aide ne les lit.
  return {
    nom,
    referenceMerimee: record.reference,
    commune: record.commune_actuelle || record.commune_forme_index,
    codeInsee: record.cog_insee_lors_de_la_protection || undefined,
    departement: record.departement_en_lettres,
    region: regionValue as Region,
    protection,
    dateProtection,
    typeProtection,
    siecleConstruction:
      record.format_abrege_du_siecle_de_construction ||
      record.siecle_de_la_campagne_principale_de_construction ||
      undefined,
    proprietaire: proprietaires.length > 0 ? proprietaires : undefined,
    descriptionGenerale: record.precision_de_la_protection || undefined,
    typeEdifice: typesEdifice.length > 0 ? typesEdifice : undefined,
    merimeeDomaine: record.domaine?.trim() || undefined,
  };
}

/**
 * Applique une notice sur une fiche déjà entamée : la recherche est désormais
 * sur le même écran que les champs, l'utilisateur a pu en remplir avant.
 *
 * Tout ce que Mérimée décrit est remplacé, même vide, pour qu'aucune date ou
 * référence d'un monument choisi auparavant ne survive. Deux exceptions : l'état
 * sanitaire, que Mérimée ignore, et le propriétaire quand la notice ne permet
 * pas de le deviner : on garde alors celui que l'utilisateur a choisi.
 *
 * Les types d'édifice, eux, sont remplacés même quand la notice n'en donne
 * aucun : un type resté d'une autre notice répondrait à tort aux questions sur
 * la nature du bien. L'affectation au culte ne survit que si les types cochés
 * ne changent pas, le style roman que si la notice est la même.
 */
export function appliquerMerimee(fiche: FicheMonument, notice: FicheMonument): FicheMonument {
  const avant = [...typesCoches(fiche)].sort().join();
  const apres = [...typesCoches(notice)].sort().join();
  const memeType = apres !== '' && apres === avant;
  const memeNotice = !!notice.referenceMerimee && notice.referenceMerimee === fiche.referenceMerimee;
  return {
    ...fiche,
    ...notice,
    proprietaire: notice.proprietaire ?? fiche.proprietaire,
    etatConservation: fiche.etatConservation,
    typeEdifice: notice.typeEdifice,
    affecteAuCulte: memeType ? fiche.affecteAuCulte : undefined,
    merimeeDomaine: notice.merimeeDomaine,
    architectureRomane: memeNotice ? fiche.architectureRomane : undefined,
  };
}

/** Libellé court de la protection d'une notice (pas d'enum côté API). */
export function protectionDeNotice(typologie: string | undefined): string {
  const t = (typologie ?? '').toLowerCase();
  if (/(?:^|[^a-zà-ÿ])classé/.test(t)) return 'Classé MH';
  if (/(?:^|[^a-zà-ÿ])inscrit/.test(t)) return 'Inscrit MH';
  return typologie || 'Protection inconnue';
}

// --- Recherche --------------------------------------------------------------

/** Minuscules sans accents, apostrophes et tirets en espaces (normalisation de la maquette). */
export function normaliserRecherche(x: string): string {
  return x
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/['’-]/g, ' ');
}

/**
 * Où la saisie apparaît dans un nom, accents et tirets ignorés : « etienne »
 * se trouve dans « Saint-Étienne » en 6, `-1` s'il n'y est pas. La
 * normalisation garde la longueur d'une chaîne composée (NFC) : l'index vaut
 * dans `nom.normalize('NFC')`.
 */
export function indexDeRecherche(nom: string, requete: string): number {
  const q = normaliserRecherche(requete).replace(/\s+/g, ' ').trim();
  if (!q) return -1;
  return normaliserRecherche(nom.normalize('NFC')).indexOf(q);
}
