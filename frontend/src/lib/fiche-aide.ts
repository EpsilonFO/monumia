/**
 * Ce que la page d'une aide et sa carte AFFICHENT, calculé une fois ici.
 *
 * Deux couches se superposent. La fiche rédigée (`aide.fiche`, `aide.carte`)
 * est le texte en langue claire ; les champs bruts de l'aide sont la
 * transcription de la source. Chaque fonction préfère la première et retombe
 * sur la seconde : une aide sans fiche s'affiche entière, en moins lisible.
 *
 * Une seule exception à cette préférence, le calendrier : il se calcule
 * toujours des dates, pour qu'une date décalée par la veille ne laisse pas un
 * texte rédigé faux en tête de page.
 */

import { AIDE_CATEGORIES, AIDE_TYPES } from '@/constants/aide-categories';
import { formatCurrency } from '@/lib/format-utils';
import type {
  Aide,
  AideConditionReglement,
  AideTexteValeur,
  ChecklistItem,
  Dossier,
  ThemeReglement,
} from '@/types';

/* ------------------------------------------------------------------ */
/* Dates                                                               */
/* ------------------------------------------------------------------ */

const MOIS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

/** « 1er juin 2026 », « 31 août 2026 ». Lu sur la chaîne ISO, sans fuseau :
 *  un `new Date('2026-08-31')` tombe la veille à l'ouest de Greenwich. */
export function dateLongue(iso: string): string {
  const [a, m, j] = iso.slice(0, 10).split('-').map(Number);
  return `${j === 1 ? '1er' : j} ${MOIS[m - 1]} ${a}`;
}

function isoDuJour(aujourdhui: Date): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${aujourdhui.getFullYear()}-${p(aujourdhui.getMonth() + 1)}-${p(aujourdhui.getDate())}`;
}

/* ------------------------------------------------------------------ */
/* Guichet                                                             */
/* ------------------------------------------------------------------ */

export type EtatGuichet = 'ouvert' | 'bientot' | 'clos' | 'attente';

export interface Guichet {
  etat: EtatGuichet;
  /** Pastille de la carte et de l'en-tête : « Clos depuis le 31 août 2026 ». */
  libelle: string;
  /** Pastille de « L'essentiel », sur fond bleu : « Clos ». */
  court: string;
  /** Ligne « Jusqu'à quand » : « Date limite passée : 15 septembre 2026 ». */
  valeur: string;
  /** Bandeau au-dessus de « En bref », quand le dépôt n'est pas possible
   *  aujourd'hui (ou que le règlement ne dit pas quand il l'est). */
  bandeau?: { titre: string; texte: string };
}

/**
 * La fenêtre de dépôt, dans les termes de la maquette. Mêmes règles que
 * `disponibilite` côté moteur : `permanent` l'emporte, une date limite du jour
 * reste ouverte, et une aide sans aucune date n'est pas close (fail-open).
 * Elle est seulement « à confirmer », sans rouge.
 */
export function guichet(
  aide: Pick<Aide, 'permanent' | 'dateOuverture' | 'dateLimite'>,
  aujourdhui: Date = new Date(),
): Guichet {
  if (aide.permanent) {
    return { etat: 'ouvert', libelle: "Ouvert toute l'année", court: 'Ouvert', valeur: "Ouvert toute l'année" };
  }
  const jour = isoDuJour(aujourdhui);
  const ouverture = aide.dateOuverture?.slice(0, 10);
  const limite = aide.dateLimite?.slice(0, 10);
  const fenetre = ouverture && limite ? `Du ${dateLongue(ouverture)} au ${dateLongue(limite)}` : null;

  if (ouverture && ouverture > jour) {
    return {
      etat: 'bientot',
      libelle: `Ouvre le ${dateLongue(ouverture)}`,
      court: 'Bientôt',
      valeur: fenetre ?? `À partir du ${dateLongue(ouverture)}`,
      bandeau: {
        titre: 'Session à venir',
        texte: `Les candidatures ouvrent le ${dateLongue(ouverture)}.`,
      },
    };
  }
  if (limite && limite < jour) {
    return {
      etat: 'clos',
      libelle: `Clos depuis le ${dateLongue(limite)}`,
      court: 'Clos',
      valeur: `Date limite passée : ${dateLongue(limite)}`,
      bandeau: {
        titre: `Clos depuis le ${dateLongue(limite)}`,
        texte: `Les candidatures sont closes depuis le ${dateLongue(limite)}. Les dates de la prochaine session ne sont pas encore publiées.`,
      },
    };
  }
  if (limite) {
    return {
      etat: 'ouvert',
      libelle: `Ouvert jusqu'au ${dateLongue(limite)}`,
      court: 'Ouvert',
      valeur: fenetre ?? `Jusqu'au ${dateLongue(limite)}`,
    };
  }
  if (ouverture) {
    return { etat: 'ouvert', libelle: 'Ouvert', court: 'Ouvert', valeur: `Depuis le ${dateLongue(ouverture)}` };
  }
  return {
    etat: 'attente',
    libelle: 'Dates à confirmer',
    court: 'Dates à venir',
    valeur: 'Dates à confirmer',
    bandeau: {
      titre: 'Dates à confirmer',
      texte: 'Le règlement ne publie pas de date limite. Renseignez-vous auprès du financeur avant de déposer.',
    },
  };
}

/** Classe de la pastille de statut (fiche-aide.css), pour chaque état. */
export const CLASSE_GUICHET: Record<EtatGuichet, string> = {
  ouvert: 'st-open',
  bientot: 'st-soon',
  clos: 'st-closed',
  attente: 'st-wait',
};

/* ------------------------------------------------------------------ */
/* Identité de l'aide                                                  */
/* ------------------------------------------------------------------ */

type AideAffichable = Pick<
  Aide,
  'nom' | 'nomCourt' | 'description' | 'organisme' | 'categorie' | 'type' | 'montantMax' | 'tauxMax' | 'carte' | 'fiche'
>;

const redige = (aide: AideAffichable) => ({ ...aide.carte, ...aide.fiche });

export function titreAide(aide: AideAffichable): string {
  return redige(aide).titre || aide.nomCourt || aide.nom;
}

/** Le financeur en quelques mots. Une aide à venir hors offre n'a plus ni
 *  financeur rédigé ni organisme : la catégorie les remplace. */
export function financeurAide(aide: AideAffichable): string {
  return (
    redige(aide).financeur
    || aide.organisme
    || AIDE_CATEGORIES.find((c) => c.value === aide.categorie)?.label
    || ''
  );
}

export function chapeauAide(aide: AideAffichable): string {
  return redige(aide).chapeau || aide.description;
}

export function libelleType(aide: Pick<Aide, 'type' | 'fiche'>): string {
  return aide.fiche?.essentiel.type?.valeur || AIDE_TYPES.find((t) => t.value === aide.type)?.label || '';
}

/** Le montant en tête de « L'essentiel » et au pied de la carte. */
export function montantAide(aide: AideAffichable): AideTexteValeur | null {
  const ecrit = redige(aide).montant;
  if (ecrit?.valeur) return ecrit;
  if (aide.tauxMax != null) {
    return {
      valeur: `Jusqu'à ${aide.tauxMax.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} %`,
      detail: aide.montantMax != null ? `Dans la limite de ${formatCurrency(aide.montantMax)}` : 'Des dépenses éligibles',
    };
  }
  if (aide.montantMax != null) return { valeur: `Jusqu'à ${formatCurrency(aide.montantMax)}`, detail: null };
  return null;
}

/* ------------------------------------------------------------------ */
/* Règlement complet                                                   */
/* ------------------------------------------------------------------ */

/** `criteres` range les gates, que la fiche rédigée ne classe dans aucun thème.
 *  `autres` n'existe que pour les aides sans fiche : leurs points n'ont pas de
 *  rubrique rédigée, et deviner la rubrique d'une condition serait un faux ami. */
export type Rubrique = 'criteres' | ThemeReglement | 'autres';

export const RUBRIQUES: { cle: Rubrique; titre: string }[] = [
  { cle: 'criteres', titre: "Critères d'éligibilité" },
  { cle: 'candidater', titre: 'Qui peut candidater' },
  { cle: 'projet', titre: 'Projets et dépenses' },
  { cle: 'montant', titre: 'Montant et cumul' },
  { cle: 'dossier', titre: 'Dossier et sélection' },
  { cle: 'apres', titre: "Après l'accord" },
  { cle: 'autres', titre: 'Les autres points' },
];

export interface PointReglement {
  id: string;
  /** Numéro affiché, continu sur toute la page (« Voir le point 5 »). */
  n: number;
  titre: string;
  /** Le texte en langue claire, ou `text` quand la fiche manque. */
  resume: string;
  quote: string | null;
  derogation: boolean;
  /** Pastille : un contrôle à faire au montage, ou une appréciation du financeur. */
  pastille: 'verifier' | 'choix' | null;
  /** Texte cherché par la recherche du règlement, aplati. */
  cherche: string;
}

export interface Reglement {
  /** Les démarches à mener avant le dépôt, en tête de page. */
  demarches: PointReglement[];
  rubriques: { cle: Rubrique; titre: string; points: PointReglement[] }[];
  total: number;
}

/** Une démarche : un point que le questionnaire ne tranche pas (`manual_check`
 *  sans effet sur le verdict), à régler par le porteur avant de déposer. Les
 *  gates, eux, sont des critères : le questionnaire les a déjà posés. */
export const estDemarche = (c: Pick<AideConditionReglement, 'kind' | 'effect'>): boolean =>
  c.kind === 'manual_check' && c.effect === 'info';

/** Aplatit pour une recherche insensible à la casse et aux accents. */
export const aplatir = (texte: string): string =>
  texte.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

/** Un titre de repli tiré du texte : sa première phrase, coupée sur un mot. */
function titreDeRepli(texte: string, max = 90): string {
  const phrase = texte.split(/(?<=[.;:])\s/)[0].replace(/[.;:]$/, '');
  if (phrase.length <= max) return phrase;
  const coupe = phrase.slice(0, max);
  return `${coupe.slice(0, coupe.lastIndexOf(' '))}…`;
}

function rubriqueDeRepli(c: AideConditionReglement): Rubrique {
  if (c.effect === 'gate') return 'criteres';
  if (c.effect === 'modulateur') return 'montant';
  if (c.kind === 'discretionary') return 'dossier';
  return 'autres';
}

/**
 * Le règlement tel que la page le range : d'abord les démarches à mener avant
 * le dépôt, puis les rubriques dans leur ordre fixe, les critères en tête. Les
 * critères ne remontent pas : le questionnaire les a posés, alors qu'une
 * démarche oubliée n'apparaît nulle part ailleurs et fait refuser le dossier.
 * La numérotation suit l'ordre d'affichage, pas celui du YAML : « point 5 »
 * doit désigner le cinquième point qu'on lit.
 */
export function reglementDe(aide: Pick<Aide, 'reglement' | 'fiche'>): Reglement {
  const points = aide.fiche?.points ?? {};
  const conditions = aide.reglement ?? [];
  const versPoint = (c: AideConditionReglement): Omit<PointReglement, 'n'> => {
    const ecrit = points[c.id];
    const titre = ecrit?.titre || titreDeRepli(c.text);
    const resume = ecrit?.resume || c.text;
    return {
      id: c.id,
      titre,
      resume,
      quote: c.quote ?? null,
      derogation: c.derogationPossible,
      // En tête, « À vérifier » redirait le titre du bloc.
      pastille:
        c.effect === 'gate' || estDemarche(c)
          ? null
          : c.kind === 'manual_check' ? 'verifier' : c.kind === 'discretionary' ? 'choix' : null,
      cherche: aplatir([titre, resume, c.quote ?? ''].join(' ')),
    };
  };

  let n = 0;
  const numeroter = (p: Omit<PointReglement, 'n'>): PointReglement => ({ ...p, n: ++n });
  const demarches = conditions.filter(estDemarche).map(versPoint).map(numeroter);
  // Un gate n'a pas de thème rédigé (skill rediger-fiche) : il va aux critères,
  // même si une fiche ancienne lui en donnait un.
  const rubriqueDe = (c: AideConditionReglement): Rubrique =>
    c.effect === 'gate' ? 'criteres' : (points[c.id]?.theme ?? rubriqueDeRepli(c));
  const rubriques = RUBRIQUES.map(({ cle, titre }) => ({
    cle,
    titre,
    points: conditions.filter((c) => !estDemarche(c) && rubriqueDe(c) === cle).map(versPoint),
  }))
    .filter((r) => r.points.length > 0)
    .map((r) => ({ ...r, points: r.points.map(numeroter) }));
  return { demarches, rubriques, total: n };
}

/* ------------------------------------------------------------------ */
/* Étapes                                                              */
/* ------------------------------------------------------------------ */

/**
 * Découpe une démarche écrite d'un seul tenant « 1. … 2. … 3. … ». On ne coupe
 * que sur des numéros qui se suivent (1, 2, 3…) : « 4 000 € » ou « avant le
 * 15 juillet » ne déclenchent rien. Le préambule avant « 1. » devient la
 * première étape.
 */
export function etapesDeLaDemarche(demarche: string): string[] {
  const lignes = demarche.split('\n').map((s) => s.trim()).filter(Boolean);
  let parts = lignes;
  if (lignes.length <= 1) {
    const texte = demarche.trim();
    const debuts: number[] = [];
    let attendu = 1;
    // L'espace qui suit le numéro est regardé, pas consommé : « … 73 18. 2. »
    // doit laisser à « 2. » l'espace qui le précède.
    for (const m of texte.matchAll(/(?:^|\s)(\d{1,2})[.)](?=\s)/g)) {
      if (Number(m[1]) === attendu) {
        debuts.push(m.index);
        attendu += 1;
      }
    }
    parts = debuts.length < 2 ? [texte] : debuts.map((d, i) => texte.slice(d, debuts[i + 1]));
    if (debuts.length >= 2 && debuts[0] > 0) parts.unshift(texte.slice(0, debuts[0]));
  }
  return parts.map((s) => s.trim().replace(/^[-•\d.)\s]+/, '')).filter(Boolean);
}

/** Les étapes affichées : rédigées si la fiche en porte, sinon la démarche
 *  découpée (une étape par morceau, sans titre). */
export function etapesAide(aide: Pick<Aide, 'fiche' | 'demarcheDescription'>): { titre: string; texte?: string | null }[] {
  if (aide.fiche?.etapes.length) return aide.fiche.etapes;
  if (!aide.demarcheDescription) return [];
  return etapesDeLaDemarche(aide.demarcheDescription).map((texte) => ({ titre: texte }));
}

/* ------------------------------------------------------------------ */
/* Pièces                                                              */
/* ------------------------------------------------------------------ */

export interface PieceAffichee {
  cle: string;
  nom: string;
  note?: string;
  url?: string;
  obligatoire: boolean;
  deposee: boolean;
}

const deposee = (item: ChecklistItem) => item.statut === 'fourni' || item.statut === 'repris';

/**
 * Les pièces de l'aide. Quand un dossier est ouvert, sa checklist fait foi : elle
 * sait ce qui est déjà déposé. Sans dossier, la liste de l'aide est informative
 * et toutes les cases sont vides.
 */
export function piecesAide(aide: Pick<Aide, 'documentsRequis' | 'fiche'>, dossier?: Dossier | null): PieceAffichee[] {
  const docs = (aide.documentsRequis ?? []).map((d) => (typeof d === 'string' ? { nom: d } : d));
  // Le nom brut reste la clé (c'est lui que porte la checklist) ; seul le
  // libellé affiché vient de la fiche rédigée.
  const libelle = (nom: string) => aide.fiche?.pieces?.[nom] || nom;
  if (dossier?.checklist.length) {
    return [...dossier.checklist]
      .sort((a, b) => a.ordre - b.ordre)
      .map((item) => {
        const doc = docs.find((d) => d.nom === item.label);
        return {
          cle: item.id,
          nom: libelle(item.label),
          note: item.description || doc?.note,
          url: doc?.url,
          obligatoire: item.obligatoire,
          deposee: deposee(item),
        };
      });
  }
  return docs.map((d, i) => ({
    cle: `${i}-${d.nom}`,
    nom: libelle(d.nom),
    note: d.note,
    url: d.url,
    obligatoire: d.obligatoire !== false,
    deposee: false,
  }));
}

/* ------------------------------------------------------------------ */
/* Liens dans un texte court                                           */
/* ------------------------------------------------------------------ */

export type Morceau = { texte: string; lien?: string };

/** Découpe un texte en morceaux dont les emails et téléphones deviennent des
 *  liens (`mailto:`, `tel:`) : la ligne « Contact » de la maquette est cliquable. */
export function lierContacts(texte: string): Morceau[] {
  const motif = /([\w.+-]+@[\w-]+(?:\.[\w-]+)+)|((?:\+33\s?|0)[1-9](?:[\s.]?\d{2}){4})/g;
  const morceaux: Morceau[] = [];
  let depuis = 0;
  for (const m of texte.matchAll(motif)) {
    if (m.index > depuis) morceaux.push({ texte: texte.slice(depuis, m.index) });
    const [trouve, email] = m;
    morceaux.push({ texte: trouve, lien: email ? `mailto:${trouve}` : `tel:${trouve.replace(/[\s.]/g, '')}` });
    depuis = m.index + trouve.length;
  }
  if (depuis < texte.length) morceaux.push({ texte: texte.slice(depuis) });
  return morceaux;
}
