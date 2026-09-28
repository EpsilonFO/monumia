/**
 * La fiche d'un monument telle que la saisit l'écran de création (maquette
 * « monumia-nouveau-monument » du designer, septembre 2026) : les regroupements
 * de ses menus, le siècle de construction, la jauge, les champs manquants.
 *
 * Tout ce qui décide est ici, sans React, pour être testé. Les VALEURS sont
 * celles du produit (`ProtectionLevel`, `OwnershipType`, `ETATS_CONSERVATION`) :
 * la maquette n'a donné que la mise en page et les regroupements.
 */
import { OWNERSHIP_TYPES } from '@/constants/monument-options';
import { REGIONS } from '@/constants/regions';
import type { MerimeeRecord, Monument, ProtectionLevel, Region } from '@/types';

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
    rempli(fiche.siecleConstruction),
    Boolean(fiche.etatConservation),
    rempli(fiche.descriptionGenerale),
    Boolean(fiche.protection),
    ...(protectionApplicable(fiche)
      ? [rempli(fiche.dateProtection), rempli(fiche.typeProtection)]
      : []),
    Boolean(fiche.proprietaire),
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
  { libelle: 'le type de propriétaire', ok: (f) => Boolean(f.proprietaire) },
];

export function champsManquants(fiche: FicheMonument): string[] {
  return REQUIS.filter((r) => !r.ok(fiche)).map((r) => r.libelle);
}

/** Phrase sous le bouton : ce qui manque, ou `null` si la fiche est complète. */
export function phraseManquants(fiche: FicheMonument): string | null {
  const manquants = champsManquants(fiche);
  return manquants.length ? `Il manque ${manquants.join(', ')}.` : null;
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
    Boolean(fiche.proprietaire),
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

const PROPRIETAIRE_MAP: Record<string, Monument['proprietaire']> = {
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

  const statutRaw = record.statut_juridique_de_l_edifice?.toLowerCase().trim() ?? '';
  const proprietaireGuess =
    PROPRIETAIRE_MAP[statutRaw] ??
    Object.entries(PROPRIETAIRE_MAP).find(([k]) => statutRaw.includes(k))?.[1] ??
    undefined;

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

  // Matériaux et type de couverture ne sont plus préremplis : leurs colonnes
  // ont été droppées (migration 20260516174303) et aucune aide ne les lit.
  return {
    nom: record.titre_editorial_de_la_notice ?? '',
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
    proprietaire: proprietaireGuess,
    descriptionGenerale: record.precision_de_la_protection || undefined,
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
 */
export function appliquerMerimee(fiche: FicheMonument, notice: FicheMonument): FicheMonument {
  return {
    ...fiche,
    ...notice,
    proprietaire: notice.proprietaire ?? fiche.proprietaire,
    etatConservation: fiche.etatConservation,
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
